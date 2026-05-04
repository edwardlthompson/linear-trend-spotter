"""Cross-provider identity bundle and CMC slug resolver id mapping."""

from __future__ import annotations

import json
from pathlib import Path

from utils.cmc_slug_resolver import CmcSlugResolver
from utils.cross_provider_identity import (
    attach_identity_bundles,
    build_identity_bundle,
    polygon_crypto_agg_ticker,
)
from utils.scan_artifacts import build_public_qualified_snapshot


def test_polygon_ticker_format() -> None:
    assert polygon_crypto_agg_ticker("btc") == "X:BTCUSD"
    assert polygon_crypto_agg_ticker("") is None


def test_build_identity_coingecko_path() -> None:
    b = build_identity_bundle(
        {
            "symbol": "ADA",
            "cg_id": "cardano",
            "cmc_slug": "cardano",
            "cmc_id": 2010,
            "provider_symbol_resolution": "direct",
            "cmc_slug_resolution": "map_name_unique",
            "ohlcv_source": "coingecko_cache",
        },
        top_coins_provider="coingecko",
    )
    assert b["cg_id"] == "cardano"
    assert b["cmc_id"] == 2010
    assert b["cmc_slug"] == "cardano"
    assert b["polygon_ticker"] == "X:ADAUSD"
    assert b["top_coins_provider"] == "coingecko"


def test_build_identity_cmc_listings_slug() -> None:
    b = build_identity_bundle(
        {
            "symbol": "BTC",
            "cg_id": "bitcoin",
            "slug": "bitcoin",
            "cmc_id": 1,
            "cmc_slug": "bitcoin",
            "provider_symbol_resolution": "direct",
        },
        top_coins_provider="cmc",
    )
    assert b["cmc_slug"] == "bitcoin"
    assert b["cmc_id"] == 1


def test_attach_identity_bundles() -> None:
    rows: list[dict] = [
        {
            "symbol": "X",
            "gecko_id": "x",
            "ohlcv_source": "polygon_api",
        }
    ]
    attach_identity_bundles(rows, top_coins_provider="coingecko")
    assert "identity" in rows[0]
    assert rows[0]["identity"]["cg_id"] == "x"
    assert rows[0]["identity"]["ohlcv_source"] == "polygon_api"


def test_public_snapshot_includes_identity() -> None:
    rows = [
        {
            "symbol": "x",
            "name": "X",
            "slug": "x",
            "gains": {"7d": 0.0, "30d": 0.0},
            "uniformity_score": 1.0,
            "health_score": 50,
            "identity": {
                "cg_id": "x",
                "cmc_id": None,
                "cmc_slug": None,
                "polygon_ticker": "X:XUSD",
                "top_coins_provider": "coingecko",
            },
        }
    ]
    payload = build_public_qualified_snapshot(rows, field_set="minimal", scan_interval_seconds=3600)
    assert payload["coins"][0]["identity"]["polygon_ticker"] == "X:XUSD"


def test_cmc_slug_resolver_learns_cmc_id(tmp_path: Path) -> None:
    r = CmcSlugResolver(tmp_path, map_cache_file="m.json", learn_file="l.json")
    r._rebuild_index_from_rows(
        [
            {"symbol": "ABC", "name": "Alpha", "slug": "alpha-coin", "id": 4242},
        ]
    )
    slug, cid, tag = r.resolve_identity(symbol="ABC", name="Alpha", gecko_id="alpha-gecko")
    assert slug == "alpha-coin"
    assert cid == 4242
    assert tag == "map_symbol_unique"
    assert r.gecko_to_slug.get("alpha-gecko") == "alpha-coin"
    assert r.gecko_to_cmc_id.get("alpha-gecko") == 4242

    r.save_learned_if_dirty()
    raw = json.loads((tmp_path / "l.json").read_text(encoding="utf-8"))
    assert raw["gecko_id_to_cmc_slug"]["alpha-gecko"] == "alpha-coin"
    assert raw["gecko_id_to_cmc_id"]["alpha-gecko"] == 4242

    r2 = CmcSlugResolver(tmp_path, map_cache_file="m.json", learn_file="l.json")
    r2.load()
    assert r2.gecko_to_cmc_id.get("alpha-gecko") == 4242
