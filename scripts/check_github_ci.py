#!/usr/bin/env python3
"""
Milestone gate: exit 0 only if required GitHub Actions workflows on branch `main`
completed successfully: CI, Security Scan, CodeQL.

Requires one of:
  - GitHub CLI `gh` in PATH, authenticated (`gh auth login`).
  - Environment variable `GITHUB_TOKEN` (or `GH_TOKEN`) with `repo` + `actions:read`.

Usage:
  python scripts/check_github_ci.py
  python scripts/check_github_ci.py --branch main
  python scripts/check_github_ci.py --wait 300

See docs/EXECUTION_PLAN.md and BUILD_PLAN.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REQUIRED_WORKFLOWS = ("CI", "Security Scan", "CodeQL")


def _parse_origin_url(raw: str) -> tuple[str, str] | None:
    raw = raw.strip()
    m = re.match(r"https://github\.com/([^/]+)/([^/.]+)", raw, re.I)
    if m:
        return m.group(1), m.group(2).removesuffix(".git")
    m = re.match(r"git@github\.com:([^/]+)/([^/.]+)", raw, re.I)
    if m:
        return m.group(1), m.group(2).removesuffix(".git")
    return None


def _owner_repo_from_git() -> tuple[str, str]:
    try:
        raw = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"FAIL: could not read git remote origin: {e}", file=sys.stderr)
        sys.exit(1)
    parsed = _parse_origin_url(raw)
    if not parsed:
        print(f"FAIL: unsupported origin URL: {raw.strip()!r}", file=sys.stderr)
        sys.exit(1)
    return parsed


def _fetch_runs_gh(branch: str) -> list[dict] | None:
    try:
        proc = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--branch",
                branch,
                "--limit",
                "30",
                "--json",
                "workflowName,conclusion,status,url,createdAt",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip() or "gh_error", file=sys.stderr)
        sys.exit(1)
    return json.loads(proc.stdout or "[]")


def _fetch_runs_api(owner: str, repo: str, branch: str) -> list[dict]:
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        print(
            "FAIL: install GitHub CLI (`gh`) and run `gh auth login`, or set GITHUB_TOKEN / GH_TOKEN.",
            file=sys.stderr,
        )
        sys.exit(1)
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?branch={branch}&per_page=30"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"FAIL: api_http_{e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"FAIL: api_error: {e}", file=sys.stderr)
        sys.exit(1)
    runs = payload.get("workflow_runs") or []
    return [
        {
            "workflowName": r.get("name") or "",
            "status": r.get("status") or "",
            "conclusion": r.get("conclusion") or "",
            "url": r.get("html_url") or "",
        }
        for r in runs
    ]


def _latest_by_workflow(runs: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for run in runs:
        name = str(run.get("workflowName") or "")
        if name not in REQUIRED_WORKFLOWS:
            continue
        if name not in latest:
            latest[name] = run
    return latest


def _evaluate(latest: dict[str, dict]) -> tuple[int, list[str]]:
    messages: list[str] = []
    pending = 0
    failed = 0

    for wf in REQUIRED_WORKFLOWS:
        run = latest.get(wf)
        if not run:
            messages.append(f"WAIT {wf}: no run yet")
            pending += 1
            continue
        status = str(run.get("status") or "")
        conclusion = str(run.get("conclusion") or "")
        url = str(run.get("url") or "")
        if status != "completed":
            messages.append(f"WAIT {wf} ({status}): {url}")
            pending += 1
            continue
        if conclusion != "success":
            messages.append(f"FAIL {wf} ({conclusion}): {url}")
            failed += 1
        else:
            messages.append(f"OK {wf}: {url}")

    if failed > 0:
        return 1, messages
    if pending > 0:
        return 2, messages
    return 0, messages


def main() -> int:
    p = argparse.ArgumentParser(description="Verify required GitHub Actions workflows are green.")
    p.add_argument("--branch", default="main", help="Branch to check (default: main)")
    p.add_argument("--wait", type=int, default=0, help="Poll up to N seconds for pending runs")
    args = p.parse_args()

    deadline = time.time() + max(0, args.wait)

    while True:
        runs = _fetch_runs_gh(args.branch)
        if runs is None:
            owner, repo = _owner_repo_from_git()
            runs = _fetch_runs_api(owner, repo, args.branch)

        code, messages = _evaluate(_latest_by_workflow(runs))
        for msg in messages:
            print(msg)

        if code == 0:
            print(f"All {len(REQUIRED_WORKFLOWS)} required workflows passed on GitHub")
            return 0
        if code == 1:
            return 1
        if args.wait <= 0 or time.time() >= deadline:
            print("INCOMPLETE: re-run with --wait 300")
            return code
        time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
