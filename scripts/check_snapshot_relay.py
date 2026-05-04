#!/usr/bin/env python3
"""Operator helper: verify snapshot relay wiring (GET /relay-health, optional POST smoke test).

Typical use (from Render **worker** shell, where env vars are set):
  python3 scripts/check_snapshot_relay.py

Override / local use:
  python3 scripts/check_snapshot_relay.py \\
    --relay-url "https://YOUR-SNAPSHOT.onrender.com" \\
    --secret "$QUALIFIED_SNAPSHOT_RELAY_SECRET"

Optional smoke POST (overwrites relay snapshot with a *tiny* JSON document):
  python3 scripts/check_snapshot_relay.py --smoke-post --i-am-sure

Exit codes:
  0  healthy enough for your selected flags
  2  HTTP / network failure
  3  validation failure (missing file, auth misconfig, etc.)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _read_relay_health(base: str, timeout: float) -> dict[str, Any]:
    url = f"{base.rstrip('/')}/relay-health"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _post_ingest(base: str, secret: str, body: bytes, timeout: float) -> tuple[int, str]:
    url = f"{base.rstrip('/')}/internal/ingest-snapshot"
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.getcode() or 0), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as he:
        return int(he.code), (he.read() or b"").decode("utf-8", errors="replace")


def _default_data_dir() -> str:
    return (os.getenv("DATA_DIR", "").strip() or os.getcwd()).strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Check snapshot relay /relay-health (+ optional POST smoke test).")
    p.add_argument(
        "--relay-url",
        default=os.getenv("QUALIFIED_SNAPSHOT_RELAY_URL", "").strip(),
        help="Snapshot relay base URL (no path). Default: env QUALIFIED_SNAPSHOT_RELAY_URL.",
    )
    p.add_argument(
        "--secret",
        default=os.getenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "").strip(),
        help="Shared ingest secret. Default: env QUALIFIED_SNAPSHOT_RELAY_SECRET.",
    )
    p.add_argument("--timeout", type=float, default=45.0, help="HTTP timeout seconds.")
    p.add_argument(
        "--require-file",
        action="store_true",
        help="Exit non-zero if relay-health reports has_snapshot_file=false.",
    )
    p.add_argument(
        "--smoke-post",
        action="store_true",
        help="POST a tiny JSON body to /internal/ingest-snapshot (overwrites relay snapshot).",
    )
    p.add_argument(
        "--i-am-sure",
        action="store_true",
        help="Required alongside --smoke-post (safety guard).",
    )
    p.add_argument(
        "--smoke-path",
        default="",
        help="If set, read this file's bytes and POST it (must be valid JSON). "
        "Otherwise POST a minimal placeholder JSON.",
    )
    args = p.parse_args()

    base = str(args.relay_url or "").strip().rstrip("/")
    if not base:
        print("ERROR: missing --relay-url / QUALIFIED_SNAPSHOT_RELAY_URL", file=sys.stderr)
        return 3

    print(f"Relay base: {base}")

    try:
        health = _read_relay_health(base, timeout=args.timeout)
    except Exception as e:
        print(f"ERROR: GET /relay-health failed: {e}", file=sys.stderr)
        return 2

    print("relay-health:")
    print(json.dumps(health, indent=2, sort_keys=True))

    if not bool(health.get("ingest_auth_configured")):
        print("WARN: relay reports ingest_auth_configured=false (QUALIFIED_SNAPSHOT_RELAY_SECRET unset on snapshot service).")

    if args.require_file and not bool(health.get("has_snapshot_file")):
        print("ERROR: --require-file set but has_snapshot_file is false", file=sys.stderr)
        return 3

    if args.smoke_post:
        if not args.i_am_sure:
            print("ERROR: refusing --smoke-post without --i-am-sure", file=sys.stderr)
            return 3
        secret = str(args.secret or "").strip()
        if not secret:
            print("ERROR: missing --secret / QUALIFIED_SNAPSHOT_RELAY_SECRET for POST", file=sys.stderr)
            return 3

        smoke_path = str(args.smoke_path or "").strip()
        if smoke_path:
            body = open(smoke_path, "rb").read()
        else:
            placeholder = {
                "schema_version": 1,
                "updated_at": "1970-01-01T00:00:00Z",
                "field_set": "minimal",
                "scan_interval_seconds": 3600,
                "coins": [],
                "_note": "scripts/check_snapshot_relay.py smoke POST — replace with real worker snapshot.",
            }
            body = json.dumps(placeholder, separators=(",", ":")).encode("utf-8")

        code, text = _post_ingest(base, secret, body=body, timeout=max(args.timeout, 120.0))
        print(f"POST /internal/ingest-snapshot -> HTTP {code}")
        if text:
            print(text[:2000])

        if code != 200:
            return 2

        try:
            health2 = _read_relay_health(base, timeout=args.timeout)
        except Exception as e:
            print(f"ERROR: GET /relay-health after POST failed: {e}", file=sys.stderr)
            return 2

        print("relay-health (after POST):")
        print(json.dumps(health2, indent=2, sort_keys=True))

        if not bool(health2.get("has_snapshot_file")):
            print("ERROR: POST succeeded but has_snapshot_file still false", file=sys.stderr)
            return 3

    # Friendly hint for humans.
    print(f"\nDATA_DIR (for reference): {_default_data_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
