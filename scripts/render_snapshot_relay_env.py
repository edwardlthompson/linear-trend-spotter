#!/usr/bin/env python3
"""Set QUALIFIED_SNAPSHOT_RELAY_* on Render worker + snapshot services via the REST API.

Render's PUT /services/{id}/env-vars **replaces all** variables for that service. This script
therefore **lists existing env vars first**, merges in the relay keys, then PUTs the combined
list so other keys (API tokens, etc.) are preserved as long as the API returns their values.

Secrets: if the list endpoint returns empty values for sensitive keys, those entries may be
lost when re-sending. If the script detects any env entry with a missing value, it aborts
unless you pass **--i-understand-risk** (unsafe).

What still cannot be automated via this API:
  - Editing **config.json** on the worker disk (**PUBLIC_QUALIFIED_SNAPSHOT_ENABLED**): commit
    it in the repo, use Render Shell, or another deploy path.
  - Anything requiring the Render dashboard UI only.

Prerequisites:
  - **RENDER_API_KEY** (Dashboard / Account Settings / API Keys) with access to the workspace.
  - **requests** (`pip install requests` if needed).

Examples:
  # Print service IDs and planned changes only
  set RENDER_API_KEY=...
  python scripts/render_snapshot_relay_env.py --dry-run

  # Generate a random secret, apply to both services (after review)
  python scripts/render_snapshot_relay_env.py --apply --generate-secret

  # Use an existing secret (same on worker + snapshot)
  python scripts/render_snapshot_relay_env.py --apply --secret "YOUR_LONG_RANDOM_SECRET"
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from typing import Any

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

API_BASE = "https://api.render.com/v1"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def list_services(session: requests.Session, token: str) -> list[dict[str, Any]]:
    """Flatten Render's paginated response (each row is often ``{cursor, service}``)."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = session.get(f"{API_BASE}/services", headers=_headers(token), params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            page_cursor: str | None = None
            for item in data:
                if not isinstance(item, dict):
                    continue
                svc = item.get("service")
                if isinstance(svc, dict):
                    out.append(svc)
                elif item.get("id"):
                    out.append(item)
                page_cursor = item.get("cursor") or page_cursor
            cursor = page_cursor
            if not cursor:
                break
            continue
        if isinstance(data, dict):
            items = data.get("service") or data.get("services") or data.get("items") or []
            if isinstance(items, list):
                out.extend(items)
            cursor = data.get("cursor") or data.get("nextCursor")
            if not cursor:
                break
            continue
        break
    return out


def find_service_id(services: list[dict[str, Any]], name: str) -> str:
    for s in services:
        if s.get("name") == name:
            sid = s.get("id")
            if sid:
                return str(sid)
    raise SystemExit(f"Service not found: {name!r}. Check name and API key workspace.")


def fetch_env_vars(session: requests.Session, token: str, service_id: str) -> list[dict[str, str]]:
    """Return [{'key': str, 'value': str}, ...] from paginated GET."""
    raw: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        r = session.get(
            f"{API_BASE}/services/{service_id}/env-vars",
            headers=_headers(token),
            params=params,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        next_cursor: str | None = None
        if isinstance(data, list):
            chunk = data
        elif isinstance(data, dict):
            chunk = data.get("envVars") or data.get("items") or []
            next_cursor = data.get("cursor") or data.get("nextCursor")
        else:
            chunk = []
        raw.extend(chunk)
        cursor = next_cursor
        if not cursor:
            break
    out: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        k = row.get("key")
        if not k:
            continue
        val = row.get("value")
        out.append({"key": str(k), "value": "" if val is None else str(val)})
    return out


def merge_relay_vars(
    existing: list[dict[str, str]],
    *,
    relay_url: str | None,
    relay_secret: str,
    for_snapshot_only: bool,
) -> list[dict[str, str]]:
    by_key: dict[str, str] = {e["key"]: e["value"] for e in existing}
    by_key["QUALIFIED_SNAPSHOT_RELAY_SECRET"] = relay_secret
    if not for_snapshot_only:
        by_key["QUALIFIED_SNAPSHOT_RELAY_URL"] = relay_url or ""
    return [{"key": k, "value": v} for k, v in sorted(by_key.items())]


def put_env_vars(
    session: requests.Session, token: str, service_id: str, env_vars: list[dict[str, str]]
) -> None:
    r = session.put(
        f"{API_BASE}/services/{service_id}/env-vars",
        headers=_headers(token),
        data=json.dumps(env_vars),
        timeout=120,
    )
    if not r.ok:
        raise SystemExit(f"PUT env-vars failed {r.status_code}: {r.text[:2000]}")


def main() -> None:
    p = argparse.ArgumentParser(
        prog="render_snapshot_relay_env.py",
        description=(
            "Merge QUALIFIED_SNAPSHOT_RELAY_* into Render worker and snapshot services "
            "(requires RENDER_API_KEY). See module docstring at top of file for full docs."
        ),
    )
    p.add_argument("--worker-name", default="linear-trend-spotter-worker")
    p.add_argument("--snapshot-name", default="linear-trend-spotter-snapshot")
    p.add_argument(
        "--relay-url",
        default="https://linear-trend-spotter-snapshot.onrender.com",
        help="QUALIFIED_SNAPSHOT_RELAY_URL on the worker (no path).",
    )
    p.add_argument(
        "--secret",
        default=os.getenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", ""),
        help="Shared secret; default: env QUALIFIED_SNAPSHOT_RELAY_SECRET.",
    )
    p.add_argument(
        "--generate-secret",
        action="store_true",
        help="Generate a random hex secret (print it once).",
    )
    p.add_argument("--dry-run", action="store_true", help="Do not call PUT.")
    p.add_argument("--apply", action="store_true", help="Apply changes (PUT).")
    p.add_argument(
        "--i-understand-risk",
        action="store_true",
        help="Allow PUT when some existing env values are empty (may drop masked secrets).",
    )
    args = p.parse_args()

    token = os.getenv("RENDER_API_KEY", "").strip()
    if not token:
        sys.exit("Set RENDER_API_KEY (Render Dashboard / Account Settings / API Keys).")

    secret = args.secret.strip()
    if args.generate_secret:
        secret = secrets.token_hex(32)
        print(f"Generated QUALIFIED_SNAPSHOT_RELAY_SECRET (save this): {secret}")
    if args.apply and not secret:
        sys.exit("Provide --secret, set QUALIFIED_SNAPSHOT_RELAY_SECRET, or use --generate-secret.")
    if not secret:
        secret = "__dry_run_placeholder__"

    if args.apply and args.dry_run:
        sys.exit("Use only one of --apply or --dry-run.")

    session = requests.Session()
    services = list_services(session, token)
    worker_id = find_service_id(services, args.worker_name)
    snapshot_id = find_service_id(services, args.snapshot_name)

    print(f"Worker service id:    {worker_id} ({args.worker_name})")
    print(f"Snapshot service id: {snapshot_id} ({args.snapshot_name})")

    w_env = fetch_env_vars(session, token, worker_id)
    s_env = fetch_env_vars(session, token, snapshot_id)

    def check_missing(vals: list[dict[str, str]]) -> list[str]:
        return [e["key"] for e in vals if e["value"] == ""]

    w_miss = check_missing(w_env)
    s_miss = check_missing(s_env)
    if (w_miss or s_miss) and not args.i_understand_risk:
        print(
            "Aborting: API returned empty value(s) for keys (often masked secrets):\n"
            f"  worker:   {w_miss}\n"
            f"  snapshot: {s_miss}\n"
            "Re-run with --i-understand-risk only if you accept possible loss of those vars,\n"
            "or set variables manually in the dashboard.",
            file=sys.stderr,
        )
        sys.exit(2)

    w_merged = merge_relay_vars(w_env, relay_url=args.relay_url, relay_secret=secret, for_snapshot_only=False)
    s_merged = merge_relay_vars(s_env, relay_url=None, relay_secret=secret, for_snapshot_only=True)

    print("\nWorker env updates:")
    print(f"  QUALIFIED_SNAPSHOT_RELAY_URL={args.relay_url}")
    print("  QUALIFIED_SNAPSHOT_RELAY_SECRET=<set>")
    print("\nSnapshot env updates:")
    print("  QUALIFIED_SNAPSHOT_RELAY_SECRET=<same as worker>")

    if args.dry_run or not args.apply:
        print("\nDry run: no PUT. Pass --apply to write to Render.")
        return

    put_env_vars(session, token, worker_id, w_merged)
    put_env_vars(session, token, snapshot_id, s_merged)
    print("\nDone. Render will redeploy services after env changes. Enable PUBLIC_QUALIFIED_SNAPSHOT in worker config.json separately.")


if __name__ == "__main__":
    main()
