from __future__ import annotations

import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "dashboard" / "icons" / "exchanges"
COINGECKO_IDS = {
    "coinbase.png": "gdax",
    "kraken.png": "kraken",
    "mexc.png": "mxc",
}


def fetch_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def download(url: str, out: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return False
            data = resp.read()
            if not data:
                return False
        out.write_bytes(data)
        return True
    except Exception:
        return False


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    fail = 0
    for filename, gecko_id in COINGECKO_IDS.items():
        meta = fetch_json(f"https://api.coingecko.com/api/v3/exchanges/{gecko_id}")
        url = str((meta or {}).get("image") or "").strip()
        if not url:
            fail += 1
            continue
        if download(url, OUT_DIR / filename):
            ok += 1
        else:
            fail += 1
    print(f"Downloaded: {ok}")
    print(f"Failed: {fail}")
    print(f"Output dir: {OUT_DIR}")


if __name__ == "__main__":
    main()
