"""Optional per-scan API cost artifact (Milestone J3)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Official commercial / plan pages (map scanner HTTP counts to your SKU).
COINGECKO_API_PRICING_URL = "https://www.coingecko.com/en/api/pricing"
POLYGON_IO_PRICING_URL = "https://polygon.io/pricing"
COINMARKETCAP_API_PRICING_URL = "https://coinmarketcap.com/api/pricing"


def read_last_completed_coingecko_http_total(metrics_path: Path) -> int | None:
    """Last entry in metrics.json history (prior scan), for J4 degrade gate."""
    if not metrics_path.exists():
        return None
    try:
        raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            return None
        last = raw[-1]
        counts = last.get("counts") if isinstance(last, dict) else None
        if not isinstance(counts, dict):
            return None
        v = counts.get("coingecko_http_total")
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def build_api_cost_panel_for_snapshot(
    metrics_summary: dict[str, Any],
    *,
    coingecko_monthly_http_cap: int = 0,
    polygon_monthly_http_cap: int = 0,
    cmc_monthly_http_cap: int = 0,
) -> dict[str, Any]:
    """Build read-only ``api_cost_panel`` for the public snapshot (dashboard health strip).

    Counts come from live ``metrics`` HTTP counters (``coingecko_http_*``, ``polygon_http_*``,
    ``cmc_http_*``). Optional monthly caps are **operator-configured** limits (e.g. max REST calls
    per month on your paid tier); compare to vendor docs at each ``pricing_url``.
    When a cap > 0, ``pct_of_monthly_budget`` is ``this_scan_http / cap * 100`` (single-scan share).
    """
    counts = dict(metrics_summary.get("counts") or {})

    def pct(scan_calls: int, cap: int) -> float | None:
        if cap <= 0 or scan_calls < 0:
            return None
        return round(100.0 * float(scan_calls) / float(cap), 5)

    cg_total = int(counts.get("coingecko_http_total", 0))
    cg_breakdown: list[dict[str, Any]] = []
    for key in sorted(counts):
        if not key.startswith("coingecko_http_") or key == "coingecko_http_total":
            continue
        cg_breakdown.append(
            {"suffix": key.removeprefix("coingecko_http_"), "count": int(counts[key])},
        )

    poly_total = int(counts.get("polygon_http_total", 0))
    poly_breakdown: list[dict[str, Any]] = []
    for key in ("polygon_http_aggs", "polygon_http_other"):
        if key in counts:
            poly_breakdown.append(
                {"suffix": key.removeprefix("polygon_http_"), "count": int(counts[key])},
            )

    cmc_total = int(counts.get("cmc_http_total", 0))
    cmc_breakdown: list[dict[str, Any]] = []
    for key in sorted(counts):
        if not key.startswith("cmc_http_") or key == "cmc_http_total":
            continue
        cmc_breakdown.append(
            {"suffix": key.removeprefix("cmc_http_"), "count": int(counts[key])},
        )

    sources: list[dict[str, Any]] = [
        {
            "id": "coingecko",
            "name": "CoinGecko",
            "pricing_url": COINGECKO_API_PRICING_URL,
            "this_scan_http": cg_total,
            "breakdown": cg_breakdown,
            "monthly_budget_http": int(coingecko_monthly_http_cap) if coingecko_monthly_http_cap > 0 else None,
            "pct_of_monthly_budget": pct(cg_total, int(coingecko_monthly_http_cap)),
        },
        {
            "id": "polygon",
            "name": "Polygon.io",
            "pricing_url": POLYGON_IO_PRICING_URL,
            "this_scan_http": poly_total,
            "breakdown": poly_breakdown,
            "monthly_budget_http": int(polygon_monthly_http_cap) if polygon_monthly_http_cap > 0 else None,
            "pct_of_monthly_budget": pct(poly_total, int(polygon_monthly_http_cap)),
        },
        {
            "id": "coinmarketcap",
            "name": "CoinMarketCap",
            "pricing_url": COINMARKETCAP_API_PRICING_URL,
            "this_scan_http": cmc_total,
            "breakdown": cmc_breakdown,
            "monthly_budget_http": int(cmc_monthly_http_cap) if cmc_monthly_http_cap > 0 else None,
            "pct_of_monthly_budget": pct(cmc_total, int(cmc_monthly_http_cap)),
        },
    ]

    return {
        "schema_version": 1,
        "note": (
            "Per-source HTTP request counts from this scan (metrics H0/J3); included in every public snapshot. "
            "Optional monthly_budget_http is your configured cap; use pricing_url to map plans/credits."
        ),
        "sources": sources,
    }


def build_scan_costs_payload(metrics_summary: dict[str, Any]) -> dict[str, Any]:
    counts = dict(metrics_summary.get("counts") or {})
    coingecko = {k: int(v) for k, v in counts.items() if k.startswith("coingecko_http_")}
    out: dict[str, Any] = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "coingecko_http": coingecko,
        "polygon_http_total": int(counts.get("polygon_http_total", 0)),
        "polygon_http_aggs": int(counts.get("polygon_http_aggs", 0)),
        "polygon_http_other": int(counts.get("polygon_http_other", 0)),
        "cmc_http_total": int(counts.get("cmc_http_total", 0)),
        "cmc_http_listings": int(counts.get("cmc_http_listings", 0)),
        "cmc_http_ohlcv": int(counts.get("cmc_http_ohlcv", 0)),
        "cmc_http_other": int(counts.get("cmc_http_other", 0)),
        "cache_hits": dict(metrics_summary.get("cache_hits") or {}),
        "cache_misses": dict(metrics_summary.get("cache_misses") or {}),
        "api_calls": dict(metrics_summary.get("api_calls") or {}),
        "coins_processed": int(metrics_summary.get("coins_processed", 0) or 0),
    }
    return out


def write_scan_costs_file(data_dir: Path, filename: str, metrics_summary: dict[str, Any]) -> None:
    payload = build_scan_costs_payload(metrics_summary)
    path = data_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmpp, path)
    finally:
        if os.path.exists(tmpp):
            try:
                os.remove(tmpp)
            except OSError:
                pass
