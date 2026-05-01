"""Resolve CoinGecko-identified coins to CoinMarketCap currency slugs for deep links.

Uses a cached copy of CMC ``GET /v1/cryptocurrency/map`` (symbol + name index) plus an
optional persistent ``gecko_id -> cmc_slug`` table learned across scans.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def _norm_name(name: str) -> str:
    return _WS.sub(" ", str(name or "").strip().casefold())


class CmcSlugResolver:
    """Build CMC /currencies/{slug}/ URLs when the app only has CoinGecko ids in ``slug``."""

    def __init__(
        self,
        data_dir: Path,
        *,
        map_cache_file: str = "cmc_cryptocurrency_map_cache.json",
        learn_file: str = "gecko_id_to_cmc_slug.json",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.map_path = self.data_dir / map_cache_file
        self.learn_path = self.data_dir / learn_file
        self.by_symbol: dict[str, list[dict[str, Any]]] = {}
        self.gecko_to_slug: dict[str, str] = {}
        self._map_fetched_at: str | None = None
        self._learn_dirty = False

    @property
    def map_entry_count(self) -> int:
        return sum(len(v) for v in self.by_symbol.values())

    def load(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_learned()
        self._load_map_cache_from_disk()

    def map_cache_is_stale(self, max_age_hours: int) -> bool:
        if not self.map_path.exists():
            return True
        if not self._map_fetched_at:
            return True
        try:
            ts = datetime.fromisoformat(self._map_fetched_at.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
            return age_h >= float(max_age_hours)
        except Exception:
            return True

    def refresh_map_from_api(self, cmc_client: Any) -> bool:
        """Paginate CMC map; returns True if at least one page stored."""
        fetch = getattr(cmc_client, "fetch_cryptocurrency_map_page", None)
        if not callable(fetch):
            return False

        all_rows: list[dict[str, Any]] = []
        start = 1
        limit = 5000
        while True:
            page = fetch(start=start, limit=limit)
            if not page:
                break
            all_rows.extend(page)
            if len(page) < limit:
                break
            start += limit
            time.sleep(2.1)

        if not all_rows:
            _logger.warning("CMC map refresh returned no rows")
            return False

        self._rebuild_index_from_rows(all_rows)
        self._map_fetched_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "fetched_at": self._map_fetched_at,
            "listing_status": "active",
            "rows": all_rows,
        }
        self.map_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        _logger.info("CMC map cache written: %s rows -> %s", len(all_rows), self.map_path.name)
        return True

    def resolve(self, *, symbol: str, name: str | None, gecko_id: str | None) -> str | None:
        gid = str(gecko_id or "").strip().lower()
        if gid and gid in self.gecko_to_slug:
            return str(self.gecko_to_slug[gid]).strip().lower() or None

        sym = str(symbol or "").strip().upper()
        if not sym:
            return None
        candidates = list(self.by_symbol.get(sym, []))
        if not candidates:
            return None
        if len(candidates) == 1:
            slug = str(candidates[0].get("slug") or "").strip().lower()
            if slug and gid:
                self._remember_pair(gid, slug)
            return slug or None

        want = _norm_name(name or "")
        if want:
            matches = [c for c in candidates if _norm_name(str(c.get("name") or "")) == want]
            if len(matches) == 1:
                slug = str(matches[0].get("slug") or "").strip().lower()
                if slug and gid:
                    self._remember_pair(gid, slug)
                return slug or None

        return None

    def learn_from_cmc_listing_coin(self, *, gecko_id: str | None, cmc_slug: str | None) -> None:
        """When top-coins came from CMC, record gecko id once mapper has filled it."""
        gid = str(gecko_id or "").strip().lower()
        slug = str(cmc_slug or "").strip().lower()
        if not gid or not slug or slug == gid:
            return
        self._remember_pair(gid, slug)

    def save_learned_if_dirty(self) -> None:
        if not self._learn_dirty:
            return
        body = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "gecko_id_to_cmc_slug": dict(sorted(self.gecko_to_slug.items())),
        }
        self.learn_path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
        self._learn_dirty = False
        _logger.info("Persisted gecko→CMC slug learn file (%s pairs)", len(self.gecko_to_slug))

    def _remember_pair(self, gecko_id: str, cmc_slug: str) -> None:
        if not gecko_id or not cmc_slug:
            return
        prev = self.gecko_to_slug.get(gecko_id)
        if prev != cmc_slug:
            self.gecko_to_slug[gecko_id] = cmc_slug
            self._learn_dirty = True

    def _load_learned(self) -> None:
        self.gecko_to_slug = {}
        if not self.learn_path.exists():
            return
        try:
            raw = json.loads(self.learn_path.read_text(encoding="utf-8"))
            m = raw.get("gecko_id_to_cmc_slug") if isinstance(raw, dict) else None
            if isinstance(m, dict):
                for k, v in m.items():
                    ks = str(k).strip().lower()
                    vs = str(v).strip().lower()
                    if ks and vs:
                        self.gecko_to_slug[ks] = vs
        except Exception as exc:
            _logger.warning("Could not load %s: %s", self.learn_path.name, exc)

    def _load_map_cache_from_disk(self) -> None:
        self.by_symbol = {}
        self._map_fetched_at = None
        if not self.map_path.exists():
            return
        try:
            raw = json.loads(self.map_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            self._map_fetched_at = str(raw.get("fetched_at") or "").strip() or None
            rows = raw.get("rows")
            if isinstance(rows, list):
                self._rebuild_index_from_rows(rows)
        except Exception as exc:
            _logger.warning("Could not load %s: %s", self.map_path.name, exc)

    def _rebuild_index_from_rows(self, rows: list[dict[str, Any]]) -> None:
        idx: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or "").strip().upper()
            slug = str(row.get("slug") or "").strip()
            name = str(row.get("name") or "").strip()
            if not sym or not slug:
                continue
            idx.setdefault(sym, []).append({"slug": slug.lower(), "name": name, "id": row.get("id")})
        self.by_symbol = idx
