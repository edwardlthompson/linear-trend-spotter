"""Active exit payload regressions."""

from __future__ import annotations

from config.settings import settings
from database.models import ActiveCoinsDatabase


def test_exit_listed_on_honors_runtime_target_exchanges(monkeypatch) -> None:
    monkeypatch.setitem(settings._config, "TARGET_EXCHANGES", ["kraken", "mexc"])

    listed_on = ActiveCoinsDatabase._listed_on_from_volume_fields(
        {
            "coinbase_volume": "$1,000",
            "kraken_volume": "$2,000",
            "mexc_volume": "$3,000",
        }
    )

    assert listed_on == ["kraken", "mexc"]
