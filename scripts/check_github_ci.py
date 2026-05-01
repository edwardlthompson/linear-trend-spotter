#!/usr/bin/env python3
"""
Milestone gate: exit 0 only if the latest GitHub Actions run for `.github/workflows/ci.yml`
on branch `main` completed successfully.

Requires one of:
  - GitHub CLI `gh` in PATH, authenticated (`gh auth login`).
  - Environment variable `GITHUB_TOKEN` (or `GH_TOKEN`) with `repo` + `actions:read` for private repos;
    public repos work with fine-grained token scoped to Actions read.

Usage:
  python scripts/check_github_ci.py
  python scripts/check_github_ci.py --branch main

See docs/EXECUTION_PLAN.md (Instructions + Non-regression).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request


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


def _check_via_gh(branch: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow=ci.yml",
                "--branch",
                branch,
                "--limit",
                "1",
                "--json",
                "conclusion,status,displayTitle,url",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return 127, "gh_not_found"
    if proc.returncode != 0:
        return proc.returncode, proc.stderr.strip() or proc.stdout.strip() or "gh_error"
    rows = json.loads(proc.stdout or "[]")
    if not rows:
        return 1, "no_runs_found"
    r = rows[0]
    status = str(r.get("status") or "")
    conclusion = str(r.get("conclusion") or "")
    title = str(r.get("displayTitle") or "")
    url = str(r.get("url") or "")
    if status != "completed":
        return 2, f"not_completed status={status} title={title!r} url={url}"
    if conclusion != "success":
        return 1, f"conclusion={conclusion!r} title={title!r} url={url}"
    return 0, f"ok conclusion=success title={title!r} url={url}"


def _check_via_api(owner: str, repo: str, branch: str) -> tuple[int, str]:
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        return 127, "no_token"
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?branch={branch}&per_page=15"
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
        return 1, f"api_http_{e.code}: {e.reason}"
    except OSError as e:
        return 1, f"api_error: {e}"

    runs = payload.get("workflow_runs") or []
    for run in runs:
        if str(run.get("path") or "") != ".github/workflows/ci.yml":
            continue
        status = str(run.get("status") or "")
        conclusion = str(run.get("conclusion") or "")
        html = str(run.get("html_url") or "")
        name = str(run.get("name") or "")
        if status != "completed":
            return 2, f"not_completed status={status} name={name!r} url={html}"
        if conclusion != "success":
            return 1, f"conclusion={conclusion!r} name={name!r} url={html}"
        return 0, f"ok conclusion=success name={name!r} url={html}"
    return 1, "no_ci_workflow_run_in_page"


def main() -> int:
    p = argparse.ArgumentParser(description="Verify latest GitHub Actions CI on branch is green.")
    p.add_argument("--branch", default="main", help="Branch to check (default: main)")
    args = p.parse_args()
    branch: str = args.branch

    code, msg = _check_via_gh(branch)
    if code != 127:
        print(msg)
        return 0 if code == 0 else code

    owner, repo = _owner_repo_from_git()
    code, msg = _check_via_api(owner, repo, branch)
    if code == 127:
        print(
            "FAIL: install GitHub CLI (`gh`) and run `gh auth login`, or set GITHUB_TOKEN / GH_TOKEN.",
            file=sys.stderr,
        )
        return 1
    print(msg)
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
