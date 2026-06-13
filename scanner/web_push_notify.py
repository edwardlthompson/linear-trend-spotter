"""Tier-B Web Push worker hook (Milestone Q21; I2 scanner extract).

When ``WEB_PUSH_NOTIFY_URL`` and ``WEB_PUSH_INTERNAL_SECRET`` are set, the worker
POSTs to the relay **only when** at least one coin **enters** or **exits** the
qualified active list churn (entries/exits). Payloads
include ``listed_on`` per coin so the relay can honor per-subscriber exchange
filters (dashboard parity). No OHLCV in payloads — short text + dashboard URL.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.settings import settings
from utils.logger import app_logger


def listed_on_for_push(coin: Mapping[str, Any] | None) -> list[str]:
    """Resolve ``listed_on`` for relay filtering (scanner snapshot + volume fallback)."""
    if not coin:
        return []
    lo = coin.get("listed_on")
    if isinstance(lo, str) and lo.strip():
        lo = [lo]
    if isinstance(lo, list) and lo:
        return sorted({str(x).strip().lower() for x in lo if str(x).strip()})
    inferred: list[str] = []
    ev = coin.get("exchange_volumes")
    if isinstance(ev, dict):
        for ex in settings.target_exchanges:
            v = ev.get(ex)
            if v is None:
                continue
            s = str(v).strip()
            if s and s.upper() != "N/A":
                inferred.append(ex)
    return sorted(set(inferred))


def _coin_push_row(coin: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not coin:
        return None
    sym = str(coin.get("symbol", "")).upper().strip()
    if not sym:
        return None
    row: dict[str, Any] = {"symbol": sym, "listed_on": listed_on_for_push(coin)}
    exit_reason = str(coin.get("exit_reason", "")).strip()
    if exit_reason:
        row["exit_reason"] = exit_reason
    return row


def _post_notify_payload(payload: dict[str, Any]) -> bool:
    base = os.getenv("WEB_PUSH_NOTIFY_URL", "").strip().rstrip("/")
    secret = os.getenv("WEB_PUSH_INTERNAL_SECRET", "").strip()
    if not base or not secret:
        return False
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = Request(
        f"{base}/internal/notify-scan",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=45) as resp:
        _ = resp.read()
    return True


def build_qualified_change_push_copy(
    *,
    entered: list[Mapping[str, Any]] | None,
    exited: list[Mapping[str, Any]] | None,
    max_symbols_per_side: int = 10,
) -> tuple[str, str]:
    """Return (title, body) for unfiltered / broadcast copy (relay may personalize)."""
    rows_in = [_coin_push_row(c) for c in (entered or [])]
    rows_out = [_coin_push_row(c) for c in (exited or [])]
    rows_in = [r for r in rows_in if r]
    rows_out = [r for r in rows_out if r]
    ent_syms = [r["symbol"] for r in rows_in]
    ext_syms = [r["symbol"] for r in rows_out]
    ent_syms = sorted(set(ent_syms))[:max_symbols_per_side]
    ext_syms = sorted(set(ext_syms))[:max_symbols_per_side]
    n_in = len(entered or [])
    n_out = len(exited or [])
    title = "Qualified list changed"
    parts: list[str] = []
    if ent_syms:
        suffix = f" (+{n_in - len(ent_syms)} more)" if n_in > len(ent_syms) else ""
        parts.append("In: " + ", ".join(ent_syms) + suffix)
    elif n_in:
        parts.append(f"In: {n_in} symbol(s)")
    if ext_syms:
        suffix = f" (+{n_out - len(ext_syms)} more)" if n_out > len(ext_syms) else ""
        parts.append("Out: " + ", ".join(ext_syms) + suffix)
    elif n_out:
        parts.append(f"Out: {n_out} symbol(s)")
    body = " · ".join(parts) if parts else "Open the qualified dashboard for the latest snapshot."
    if len(body) > 240:
        body = body[:237] + "…"
    return title, body


def maybe_notify_web_push_qualified_changes(
    entered: list[Mapping[str, Any]] | None,
    exited: list[Mapping[str, Any]] | None,
) -> None:
    """POST to optional push relay when the qualified set gained or lost members."""
    if not (entered or exited):
        return
    dashboard_url = os.getenv("WEB_PUSH_DASHBOARD_URL", "").strip()
    title, body = build_qualified_change_push_copy(entered=entered, exited=exited)
    entered_coins = [x for x in (_coin_push_row(c) for c in (entered or [])) if x]
    exited_coins = [x for x in (_coin_push_row(c) for c in (exited or [])) if x]
    payload = {
        "title": title[:120],
        "body": body[:240],
        "url": dashboard_url[:2000],
        "entered_coins": entered_coins,
        "exited_coins": exited_coins,
    }
    try:
        if _post_notify_payload(payload):
            app_logger.info(
                "🔔 Web push relay notified (qualified in=%s out=%s)",
                len(entered or []),
                len(exited or []),
            )
    except HTTPError as he:
        app_logger.warning("⚠️ Web push relay HTTP %s: %s", he.code, he.reason)
    except URLError as ue:
        app_logger.warning("⚠️ Web push relay failed: %s", ue)
    except Exception as wp_err:
        app_logger.warning("⚠️ Web push relay failed: %s", wp_err)
