#!/usr/bin/env python3
"""Provision Tier-C ntfy env vars on the Render worker via the REST API.

Generates an unguessable topic + publish token, merges ``NTFY_*`` into the worker
service env (preserving other keys), optionally verifies publish with a test POST,
and writes a local reference file (subscribe URL only — no publish token in JSON).

Prerequisites:
  - **RENDER_API_KEY** (Render Dashboard / Account Settings / API Keys).
  - **requests** (`pip install requests` if needed).

Examples:
  set RENDER_API_KEY=...
  python scripts/provision_tier_c_ntfy.py --generate --dry-run

  python scripts/provision_tier_c_ntfy.py --generate --apply \\
    --dashboard-url https://edwardlthompson.github.io/linear-trend-spotter/docs/dashboard/

  python scripts/provision_tier_c_ntfy.py --apply --topic my-topic --token my-token
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

from utils.notify_provision import build_ntfy_subscribe_url, merge_ntfy_vars, unsafe_preserved_env_keys

API_BASE = "https://api.render.com/v1"
DEFAULT_WORKER = "linear-trend-spotter-worker"
PROVISION_ARTIFACT = ".ntfy-provision.local.json"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def list_services(session: requests.Session, token: str) -> list[dict[str, Any]]:
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


def test_ntfy_publish(base_url: str, topic: str, publish_token: str) -> bool:
    url = build_ntfy_subscribe_url(base_url, topic)
    if not url:
        return False
    headers: dict[str, str] = {"Title": "Linear Trend Spotter setup test"}
    if publish_token:
        headers["Authorization"] = f"Bearer {publish_token}"
    try:
        r = requests.post(
            url,
            data="Tier-C ntfy provision test (safe to ignore).",
            headers=headers,
            timeout=30,
        )
        return r.ok
    except requests.RequestException as exc:
        print(f"WARN: ntfy test publish failed: {exc}", file=sys.stderr)
        return False


def write_provision_artifact(
    path: Path,
    *,
    subscribe_url: str,
    base_url: str,
    topic: str,
    dashboard_url: str,
) -> None:
    body = {
        "ntfy_subscribe_url": subscribe_url,
        "NTFY_BASE_URL": base_url.rstrip("/"),
        "NTFY_TOPIC": topic,
        "NTFY_DASHBOARD_URL": dashboard_url,
        "note": "Publish token is on Render only — not stored in this file.",
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(prog="provision_tier_c_ntfy.py")
    p.add_argument("--worker-name", default=DEFAULT_WORKER)
    p.add_argument("--base-url", default=os.getenv("NTFY_BASE_URL", "https://ntfy.sh"))
    p.add_argument("--topic", default=os.getenv("NTFY_TOPIC", "").strip())
    p.add_argument("--token", default=os.getenv("NTFY_TOKEN", "").strip())
    p.add_argument(
        "--dashboard-url",
        default=os.getenv("NTFY_DASHBOARD_URL", "").strip(),
        help="Click-through URL embedded in ntfy messages.",
    )
    p.add_argument("--generate", action="store_true", help="Generate random topic + token.")
    p.add_argument("--dry-run", action="store_true", help="Print planned changes only.")
    p.add_argument("--apply", action="store_true", help="PUT merged env to Render worker.")
    p.add_argument("--test-publish", action="store_true", help="POST setup test message to ntfy.")
    p.add_argument(
        "--artifact",
        default=PROVISION_ARTIFACT,
        help=f"Write subscribe URL reference JSON (default: {PROVISION_ARTIFACT}).",
    )
    p.add_argument(
        "--i-understand-risk",
        action="store_true",
        help="Allow PUT when Render API returns empty values for masked secrets.",
    )
    args = p.parse_args()

    render_token = os.getenv("RENDER_API_KEY", "").strip()
    if not render_token:
        sys.exit("Set RENDER_API_KEY (Render Dashboard / Account Settings / API Keys).")

    topic = args.topic
    publish_token = args.token
    if args.generate:
        topic = secrets.token_urlsafe(32)
        publish_token = secrets.token_urlsafe(32)
        print(f"Generated NTFY_TOPIC: {topic}")
        print(f"Generated NTFY_TOKEN (save securely): {publish_token}")

    if args.apply and not topic:
        sys.exit("Provide --topic, set NTFY_TOPIC, or use --generate.")
    if args.apply and not publish_token:
        sys.exit("Provide --token, set NTFY_TOKEN, or use --generate.")

    if args.apply and args.dry_run:
        sys.exit("Use only one of --apply or --dry-run.")

    base_url = str(args.base_url or "https://ntfy.sh").strip()
    dashboard_url = str(args.dashboard_url or "").strip()
    subscribe_url = build_ntfy_subscribe_url(base_url, topic or "dry-run-topic")

    session = requests.Session()
    services = list_services(session, render_token)
    worker_id = find_service_id(services, args.worker_name)
    print(f"Worker service id: {worker_id} ({args.worker_name})")

    w_env = fetch_env_vars(session, render_token, worker_id)
    unsafe_existing = unsafe_preserved_env_keys(w_env)
    if unsafe_existing and not args.i_understand_risk:
        print(
            "Aborting: API returned empty or masked value(s) for existing non-NTFY keys:\n"
            f"  {unsafe_existing}\n"
            "Render's env PUT replaces every variable; re-run with --i-understand-risk only "
            "if you accept possible loss of those vars.",
            file=sys.stderr,
        )
        sys.exit(2)

    merged = merge_ntfy_vars(
        w_env,
        enabled=True,
        base_url=base_url,
        topic=topic or "dry-run-topic",
        token=publish_token or "dry-run-token",
        dashboard_url=dashboard_url,
    )

    print("\nPlanned worker env updates:")
    print("  NTFY_ENABLED=true")
    print(f"  NTFY_BASE_URL={base_url.rstrip('/')}")
    print(f"  NTFY_TOPIC={topic or '<topic>'}")
    print("  NTFY_TOKEN=<set>")
    if dashboard_url:
        print(f"  NTFY_DASHBOARD_URL={dashboard_url}")
    print(f"\nPublic subscribe URL (safe for dashboard): {subscribe_url}")

    if args.dry_run or not args.apply:
        print("\nDry run: no PUT. Pass --apply to write to Render.")
        return

    put_env_vars(session, render_token, worker_id, merged)
    artifact_path = Path(args.artifact)
    write_provision_artifact(
        artifact_path,
        subscribe_url=subscribe_url,
        base_url=base_url,
        topic=topic,
        dashboard_url=dashboard_url,
    )
    print(f"\nWrote reference artifact: {artifact_path}")
    print("After the next scan, snapshot JSON will include notify_public_config.ntfy_subscribe_url.")

    if args.test_publish:
        ok = test_ntfy_publish(base_url, topic, publish_token)
        if ok:
            print("ntfy test publish: OK")
        else:
            print("WARN: ntfy test publish failed (check topic ACL / token).", file=sys.stderr)

    print("\nDone. Render will redeploy the worker after env changes.")


if __name__ == "__main__":
    main()
