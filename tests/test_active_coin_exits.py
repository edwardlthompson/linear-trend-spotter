"""Regression tests for active-coin exit metadata."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listing_inference_honors_runtime_target_exchanges(monkeypatch) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["coinbase", "kraken", "mexc"])

    listed_on = ActiveCoinsDatabase._listed_on_from_volume_fields(
        {
            "coinbase_volume": "N/A",
            "kraken_volume": "$1.2M",
            "mexc_volume": "$2.4M",
        }
    )

    assert listed_on == ["kraken", "mexc"]
