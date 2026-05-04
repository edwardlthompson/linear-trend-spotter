"""OHLCV_UNIFORMITY_SOURCE_ORDER validation."""

import pytest

from config.settings import Settings


def test_default_order_is_legacy_chain(tmp_path):
    s = Settings(config_path=str(tmp_path / "missing.json"))
    assert s.ohlcv_uniformity_source_order == ("coingecko", "polygon", "cmc")


def test_invalid_order_raises(tmp_path):
    cfg = tmp_path / "bad.json"
    cfg.write_text(
        '{"OHLCV_UNIFORMITY_SOURCE_ORDER": "coingecko,polygon"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="OHLCV_UNIFORMITY_SOURCE_ORDER"):
        Settings(config_path=str(cfg))


def test_credit_saver_permutation(tmp_path):
    cfg = tmp_path / "good.json"
    cfg.write_text(
        '{"OHLCV_UNIFORMITY_SOURCE_ORDER": "cmc,polygon,coingecko"}',
        encoding="utf-8",
    )
    s = Settings(config_path=str(cfg))
    assert s.ohlcv_uniformity_source_order == ("cmc", "polygon", "coingecko")
