"""Shared helpers for Tier-C ntfy provisioning (no Render API deps)."""

from __future__ import annotations


def build_ntfy_subscribe_url(base_url: str, topic: str) -> str:
    base = str(base_url or "https://ntfy.sh").strip().rstrip("/") or "https://ntfy.sh"
    t = str(topic or "").strip()
    if not t:
        return ""
    return f"{base}/{t}"


def merge_ntfy_vars(
    existing: list[dict[str, str]],
    *,
    enabled: bool,
    base_url: str,
    topic: str,
    token: str,
    dashboard_url: str,
) -> list[dict[str, str]]:
    """Merge NTFY_* keys into Render env list (sorted by key)."""
    by_key: dict[str, str] = {e["key"]: e["value"] for e in existing}
    by_key["NTFY_ENABLED"] = "true" if enabled else "false"
    by_key["NTFY_BASE_URL"] = base_url.rstrip("/") or "https://ntfy.sh"
    by_key["NTFY_TOPIC"] = topic
    by_key["NTFY_TOKEN"] = token
    if dashboard_url:
        by_key["NTFY_DASHBOARD_URL"] = dashboard_url
    return [{"key": k, "value": v} for k, v in sorted(by_key.items())]
