"""Windows system-tray notifier — polls public snapshot and toasts on list change (Q24)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from typing import Any

import requests
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
from winotify import Notification, audio

DEFAULT_POLL_S = 3600
MIN_POLL_S = 900


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        val = int(os.getenv(name, str(default)))
    except ValueError:
        val = default
    return max(minimum, val)


def _snapshot_url() -> str:
    url = os.getenv("LTS_SNAPSHOT_URL", "").strip()
    if not url:
        raise SystemExit("Set LTS_SNAPSHOT_URL to your public qualified snapshot JSON URL.")
    return url


def _target_exchanges() -> set[str]:
    raw = os.getenv("LTS_TARGET_EXCHANGES", "coinbase,kraken").strip()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _row_keys(coins: list[dict[str, Any]], exchanges: set[str]) -> set[str]:
    keys: set[str] = set()
    for coin in coins:
        if not isinstance(coin, dict):
            continue
        sym = str(coin.get("symbol", "")).upper().strip()
        if not sym:
            continue
        listed = coin.get("listed_on") or []
        if isinstance(listed, str):
            listed = [listed]
        venues = {str(x).strip().lower() for x in listed if str(x).strip()}
        if not venues:
            keys.add(f"{sym}|")
            continue
        for ex in sorted(venues & exchanges if exchanges else venues):
            keys.add(f"{sym}|{ex}")
    return keys


def _fetch_row_keys(url: str, exchanges: set[str]) -> set[str]:
    resp = requests.get(url, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    coins = data.get("coins") if isinstance(data, dict) else []
    if not isinstance(coins, list):
        return set()
    return _row_keys(coins, exchanges)


def _digest(keys: set[str]) -> str:
    blob = json.dumps(sorted(keys), separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _toast(title: str, body: str) -> None:
    note = Notification(app_id="Linear Trend Spotter", title=title[:120], msg=body[:240])
    note.set_audio(audio.Default, loop=False)
    note.show()


def _make_icon_image() -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    draw.rectangle((12, 28, 52, 36), fill=(56, 189, 248))
    return img


class TrayNotifier:
    def __init__(self) -> None:
        self._url = _snapshot_url()
        self._exchanges = _target_exchanges()
        self._poll_s = _env_int("LTS_POLL_INTERVAL_SECONDS", DEFAULT_POLL_S, MIN_POLL_S)
        self._stop = threading.Event()
        self._last_digest: str | None = None
        self._icon = Icon(
            "linear-trend-spotter",
            _make_icon_image(),
            "Linear Trend Spotter",
            menu=Menu(MenuItem("Quit", self._quit)),
        )

    def _quit(self, _icon: Icon, _item: Any) -> None:
        self._stop.set()
        self._icon.stop()

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                keys = _fetch_row_keys(self._url, self._exchanges)
                dig = _digest(keys)
                if self._last_digest is not None and dig != self._last_digest:
                    _toast("Qualified list changed", "Open the dashboard for details.")
                self._last_digest = dig
            except Exception as exc:
                print(f"poll error: {exc}", file=sys.stderr)
            self._stop.wait(self._poll_s)

    def run(self) -> None:
        t = threading.Thread(target=self._poll_loop, name="lts-tray-poll", daemon=True)
        t.start()
        self._icon.run()


def main() -> None:
    TrayNotifier().run()


if __name__ == "__main__":
    main()
