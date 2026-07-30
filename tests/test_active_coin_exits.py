"""Active coin exit metadata regressions."""

from __future__ import annotations

from database.models import ActiveCoinsDatabase
from config.settings import settings


def test_exit_listed_on_honors_runtime_target_exchanges(monkeypatch) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["mexc"])

    listed_on = ActiveCoinsDatabase._listed_on_from_volume_fields(
        {
            "coinbase_volume": "N/A",
            "kraken_volume": "N/A",
            "mexc_volume": "$2,500,000",
        }
    )

    assert listed_on == ["mexc"]
