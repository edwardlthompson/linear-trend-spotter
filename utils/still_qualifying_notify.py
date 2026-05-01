"""Optional Telegram 'still qualifying' roster with editMessageText."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from html import escape as html_escape

_logger = logging.getLogger(__name__)


def _volume_listed(raw: object) -> bool:
    if raw is None:
        return False
    s = str(raw).strip().upper()
    if not s or s in {'N/A', 'NA', 'NONE', 'NULL'}:
        return False
    try:
        return float(s) > 0
    except ValueError:
        return True


def build_still_qualifying_html(final_results: list[dict[str, Any]], max_symbols: int = 40) -> str:
    """Compact HTML body listing symbols still qualified (no roster change this run)."""
    lines: list[str] = []
    lines.append('<b>Still qualifying</b> (no new entries or exits this scan)')
    for coin in final_results[:max_symbols]:
        sym = str(coin.get('symbol', '') or '').strip().upper()
        if not sym:
            continue
        hs = coin.get('health_score')
        hs_s = f"{float(hs):.0f}" if isinstance(hs, (int, float)) else "—"
        lines.append(f"• {html_escape(sym, quote=False)} (health {html_escape(hs_s, quote=False)})")
    if len(final_results) > max_symbols:
        lines.append(f"… and {len(final_results) - max_symbols} more")
    return "\n".join(lines)


def load_message_id(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        _logger.warning('Still-qualifying state read failed (%s): %s', path, e)
        return None
    mid = data.get('message_id')
    if isinstance(mid, int) and mid > 0:
        return mid
    return None


def save_message_id(path: Path, message_id: int | None) -> None:
    payload = {'message_id': message_id}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    except OSError as e:
        _logger.warning('Still-qualifying state write failed (%s): %s', path, e)


def sync_still_qualifying_scan_message(
    telegram,
    *,
    state_path: Path,
    final_results: list[dict[str, Any]],
    entered_len: int,
    exited_len: int,
    enabled: bool,
    no_change_notifications: bool,
    quiet_suppress: bool,
) -> bool:
    """Send or edit a single roster message when the qualified set is unchanged.

    Returns True if ``send_message`` or a successful ``edit_message_text`` ran.
    """
    if not enabled or not no_change_notifications:
        return False
    if entered_len or exited_len:
        save_message_id(state_path, None)
        return False
    if quiet_suppress:
        return False
    if not final_results:
        save_message_id(state_path, None)
        return False

    text = build_still_qualifying_html(final_results)
    mid = load_message_id(state_path)
    if mid is not None:
        if telegram.edit_message_text(mid, text):
            return True
    new_mid = telegram.send_message(text)
    if new_mid:
        save_message_id(state_path, int(new_mid))
        return True
    save_message_id(state_path, None)
    return False
