"""Fetch live API credit / quota usage from vendor dashboards (optional, per scan).

Uses one HTTP GET per provider (not counted in scanner ``metrics`` HTTP tallies).

- **CoinGecko:** ``GET /api/v3/key`` (Pro or Demo host + matching auth header).
- **CoinMarketCap:** ``GET /v1/key/info`` (documented; not billed as a data call).
- **Polygon.io:** No stable public REST for monthly credits as of 2026; omitted (use
  configured ``SCAN_COST_PANEL_POLYGON_MONTHLY_HTTP_CAP`` + local ``polygon_http_*`` counts).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

_COINGECKO_DEMO_BASE = "https://api.coingecko.com/api/v3"
_COINGECKO_PRO_BASE = "https://pro-api.coingecko.com/api/v3"
_CMC_KEY_INFO = "https://pro-api.coinmarketcap.com/v1/key/info"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    logger: logging.Logger,
    label: str,
) -> dict[str, Any] | None:
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        text = (r.text or "")[:4000]
        try:
            payload = r.json()
        except Exception:
            logger.warning("%s: non-JSON HTTP %s body=%s", label, r.status_code, text[:200])
            return None
        if not isinstance(payload, dict):
            return None
        if r.status_code != 200:
            logger.info("%s: HTTP %s payload=%s", label, r.status_code, str(payload)[:300])
            return payload
        return payload
    except Exception as exc:
        logger.warning("%s: request failed: %s", label, exc)
        return None


def fetch_coingecko_key_quota(api_key: str, *, timeout: float, logger: logging.Logger) -> dict[str, Any] | None:
    key = (api_key or "").strip()
    if not key:
        return None
    if key.startswith("CG-"):
        url = f"{_COINGECKO_DEMO_BASE}/key"
        headers = {"x-cg-demo-api-key": key, "User-Agent": "Linear-Trend-Spotter/1.0"}
        label = "CoinGecko demo /key"
    else:
        url = f"{_COINGECKO_PRO_BASE}/key"
        headers = {"x-cg-pro-api-key": key, "User-Agent": "Linear-Trend-Spotter/1.0"}
        label = "CoinGecko pro /key"
    data = _fetch_json(url, headers=headers, timeout=timeout, logger=logger, label=label)
    if not isinstance(data, dict):
        return None
    st = data.get("status")
    if isinstance(st, dict) and st.get("error_code"):
        return {
            "ok": False,
            "fetched_at": _iso_now(),
            "error": str(st.get("error_message") or "CoinGecko key error"),
            "error_code": st.get("error_code"),
        }
    # Successful responses expose quota fields at the top level (CG Pro API reference).
    total = data.get("monthly_call_credit")
    if total is None:
        total = data.get("api_key_monthly_call_credit")
    used = data.get("current_total_monthly_calls")
    remaining = data.get("current_remaining_monthly_calls")
    try:
        lim = int(total) if total is not None else 0
        u = int(used) if used is not None else None
        rem = int(remaining) if remaining is not None else None
    except (TypeError, ValueError):
        lim = 0
        u = None
        rem = None
    if u is None and rem is not None and lim > 0:
        u = max(0, lim - rem)
    if lim <= 0 and u is None:
        return {
            "ok": False,
            "fetched_at": _iso_now(),
            "error": "CoinGecko /key response missing monthly_call_credit (plan may not report credits)",
        }
    return {
        "ok": True,
        "fetched_at": _iso_now(),
        "period": "monthly",
        "source": "coingecko_api_v3_key",
        "used": int(u or 0),
        "limit": int(lim),
        "remaining": int(rem) if rem is not None else max(0, lim - int(u or 0)),
        "plan_name": str(data.get("plan") or "").strip() or None,
    }


def fetch_cmc_key_quota(api_key: str, *, timeout: float, logger: logging.Logger) -> dict[str, Any] | None:
    key = (api_key or "").strip()
    if not key:
        return None
    headers = {"X-CMC_PRO_API_KEY": key, "Accept": "application/json", "User-Agent": "Linear-Trend-Spotter/1.0"}
    data = _fetch_json(_CMC_KEY_INFO, headers=headers, timeout=timeout, logger=logger, label="CMC /v1/key/info")
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    if isinstance(status, dict):
        ec = status.get("error_code")
        if ec not in (None, 0, "0"):
            err = status.get("error_message") or str(ec)
            return {
                "ok": False,
                "fetched_at": _iso_now(),
                "error": str(err),
                "error_code": ec,
            }
    inner = data.get("data")
    if not isinstance(inner, dict):
        return {
            "ok": False,
            "fetched_at": _iso_now(),
            "error": "CMC /key/info missing data object",
        }
    plan = inner.get("plan") if isinstance(inner.get("plan"), dict) else {}
    usage = inner.get("usage") if isinstance(inner.get("usage"), dict) else {}
    cur_m = usage.get("current_month") if isinstance(usage.get("current_month"), dict) else {}
    try:
        limit = int(plan.get("credit_limit_monthly") or 0)
        used = int(cur_m.get("credits_used") or 0)
        remaining = int(cur_m.get("credits_left") or 0)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "fetched_at": _iso_now(),
            "error": "CMC /key/info usage fields not parseable",
        }
    if limit <= 0:
        return {
            "ok": False,
            "fetched_at": _iso_now(),
            "error": "CMC plan has no credit_limit_monthly in /key/info",
        }
    return {
        "ok": True,
        "fetched_at": _iso_now(),
        "period": "monthly",
        "source": "coinmarketcap_v1_key_info",
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "plan_name": str(plan.get("plan_name") or plan.get("name") or "").strip() or None,
    }


def fetch_vendor_quotas(
    *,
    coingecko_key: str,
    cmc_key: str,
    timeout: float = 12.0,
    logger: logging.Logger | None = None,
) -> dict[str, dict[str, Any]]:
    """Return optional quota dicts keyed ``coingecko`` / ``coinmarketcap`` (polygon omitted)."""
    log = logger or logging.getLogger(__name__)
    out: dict[str, dict[str, Any]] = {}
    raw = os.getenv("SCAN_COST_VENDOR_QUOTA_FETCH", "true").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return out
    cg = fetch_coingecko_key_quota(coingecko_key, timeout=timeout, logger=log)
    if cg is not None:
        out["coingecko"] = cg
    cmc = fetch_cmc_key_quota(cmc_key, timeout=timeout, logger=log)
    if cmc is not None:
        out["coinmarketcap"] = cmc
    return out
