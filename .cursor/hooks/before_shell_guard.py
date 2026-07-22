#!/usr/bin/env python3
"""beforeShellExecution: deny destructive commands unless session approved. Fail-open."""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SHELL_SEPARATORS = frozenset({";", "&&", "||", "|", "&"})
SQL_CLIENTS = frozenset({"duckdb", "mariadb", "mysql", "psql", "sqlite3", "sqlcmd"})


def command_segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SHELL_SEPARATORS:
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def executable_and_args(segment: list[str]) -> tuple[str, list[str]]:
    index = 0
    while index < len(segment):
        token = segment[index]
        if "=" in token and not token.startswith(("/", "./", "../")):
            index += 1
            continue
        if token in {"command", "env", "nohup", "sudo"}:
            index += 1
            continue
        break
    if index >= len(segment):
        return "", []
    executable = Path(segment[index]).name.lower()
    return executable, [arg.lower() for arg in segment[index + 1 :]]


def destructive_operation(command: str, patterns: list[str]) -> str | None:
    """Identify configured destructive operations from executable shell syntax."""
    configured = set(patterns)
    for segment in command_segments(command):
        executable, args = executable_and_args(segment)
        if executable == "git" and args:
            if args[0] == "push":
                force_flags = {"-f", "--force", "--force-if-includes", "--force-with-lease"}
                forced = any(
                    arg in force_flags or arg.startswith("--force-with-lease=") for arg in args[1:]
                )
                operation = "git push --force" if forced else "git push"
                if operation in configured:
                    return operation
            if args[0] in {"commit", "merge", "rebase"}:
                for flag in ("--no-verify", "--no-gpg-sign"):
                    if flag in args[1:] and flag in configured:
                        return flag
        if executable == "terraform" and args[:1] == ["apply"]:
            if "terraform apply" in configured:
                return "terraform apply"
        if executable == "rm":
            options = "".join(arg.lstrip("-") for arg in args if arg.startswith("-"))
            if "r" in options and "f" in options:
                for target in ("/", "~"):
                    operation = f"rm -rf {target}"
                    if target in args and operation in configured:
                        return operation
        if executable in SQL_CLIENTS:
            sql = " ".join(args)
            if "drop table" in configured and re.search(r"\bdrop\s+table\b", sql):
                return "drop table"
            if "delete from" in configured:
                for statement in sql.split(";"):
                    is_delete = re.search(r"\bdelete\s+from\b", statement)
                    if is_delete and not re.search(r"\bwhere\b", statement):
                        return "delete from"
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"permission": "allow"}))
        return

    command = (data.get("command") or "").strip()
    if not command:
        print(json.dumps({"permission": "allow"}))
        return

    bp = ROOT / "BUILD_PLAN.md"
    if bp.is_file() and "<!-- cursor-hooks: off -->" in bp.read_text(encoding="utf-8"):
        print(json.dumps({"permission": "allow"}))
        return

    deny_path = ROOT / ".cursor/hooks/shell-denylist.txt"
    patterns: list[str] = []
    if deny_path.is_file():
        for line in deny_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line.lower())

    approved: list[str] = []
    for name in (".cursor-session-state.json", ".cursor-session-state"):
        state_path = ROOT / name
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                approved = state.get("destructive_ops_approved") or []
            except json.JSONDecodeError:
                pass
            break

    operation = destructive_operation(command, patterns)
    if operation is not None:
        if any(str(ok).strip().lower() == operation for ok in approved):
            print(json.dumps({"permission": "allow"}))
            return
        print(
            json.dumps(
                {
                    "permission": "deny",
                    "user_message": f"Blocked destructive command (hook): {command[:120]}",
                    "agent_message": (
                        "Use /push or /ship for git push approval; "
                        "set destructive_ops_approved in session state."
                    ),
                }
            )
        )
        return

    print(json.dumps({"permission": "allow"}))


if __name__ == "__main__":
    main()
