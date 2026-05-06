from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "docs" / "qualified_public_snapshot.json"
CMC_MAP_PATH = ROOT / "cmc_cryptocurrency_map_cache.json"
OUT_DIR = ROOT / "docs" / "dashboard" / "icons" / "coins"
CMC_BASE_URL = "https://s2.coinmarketcap.com/static/img/coins/64x64/{id}.png"
SPOT_BASE_URL = "https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/{sym}.png"


def load_snapshot_coins() -> list[dict]:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    coins = payload.get("coins") or []
    out: list[dict] = []
    for coin in coins:
        c = coin or {}
        sym = str(c.get("symbol") or "").strip().lower()
        slug = str(c.get("slug") or "").strip().lower()
        if sym:
            out.append({"symbol": sym, "slug": slug})
    return out


def load_cmc_rows() -> list[dict]:
    payload = json.loads(CMC_MAP_PATH.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    return [r for r in rows if isinstance(r, dict)]


def cmc_id_for_coin(coin: dict, cmc_rows: list[dict]) -> int | None:
    symbol = str(coin.get("symbol") or "").lower()
    slug = str(coin.get("slug") or "").lower()
    candidates = []
    for row in cmc_rows:
        rsym = str(row.get("symbol") or "").lower()
        if rsym != symbol:
            continue
        rid = row.get("id")
        if not isinstance(rid, int):
            continue
        rank = row.get("rank")
        rank_num = rank if isinstance(rank, (int, float)) else 10**9
        rslug = str(row.get("slug") or "").lower()
        score = 0
        if slug and rslug == slug:
            score = 1
        candidates.append((score, rank_num, rid))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    return candidates[0][2]


def download_url(url: str, out: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return False
            data = resp.read()
            if not data:
                return False
        out.write_bytes(data)
        return True
    except Exception:
        return False


def download_icon(coin: dict, cmc_rows: list[dict]) -> bool:
    symbol = str(coin.get("symbol") or "").lower()
    out = OUT_DIR / f"{symbol}.png"
    cmc_id = cmc_id_for_coin(coin, cmc_rows)
    if cmc_id is not None:
        cmc_url = CMC_BASE_URL.format(id=cmc_id)
        if download_url(cmc_url, out):
            return True
    spot_url = SPOT_BASE_URL.format(sym=urllib.parse.quote(symbol))
    return download_url(spot_url, out)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_coins = load_snapshot_coins()
    cmc_rows = load_cmc_rows()
    base_symbols = {"btc", "eth", "sol", "xrp"}
    symbols = sorted({c["symbol"] for c in snapshot_coins} | base_symbols)
    ok = 0
    fail = 0
    for sym in symbols:
        coin = next((c for c in snapshot_coins if c["symbol"] == sym), {"symbol": sym, "slug": ""})
        if download_icon(coin, cmc_rows):
            ok += 1
        else:
            fail += 1
    print(f"Downloaded: {ok}")
    print(f"Failed: {fail}")
    print(f"Output dir: {OUT_DIR}")


if __name__ == "__main__":
    main()
