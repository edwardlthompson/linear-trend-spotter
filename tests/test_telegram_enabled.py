"""TELEGRAM_ENABLED master switch (web-only vs Telegram delivery)."""

from __future__ import annotations

import json
from pathlib import Path


def test_telegram_enabled_false_from_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"TELEGRAM_ENABLED": False}), encoding="utf-8")
    from config.settings import Settings

    s = Settings(str(cfg))
    assert s.telegram_enabled is False


def test_telegram_enabled_env_overrides_config(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"TELEGRAM_ENABLED": True}), encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    from config.settings import Settings

    s = Settings(str(cfg))
    assert s.telegram_enabled is False


def test_delivery_mode_web_disables_telegram(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("DELIVERY_MODE", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"DELIVERY_MODE": "web", "TELEGRAM_ENABLED": True}),
        encoding="utf-8",
    )
    from config.settings import Settings

    s = Settings(str(cfg))
    assert s.delivery_mode == "web"
    assert s.telegram_enabled is False


def test_delivery_mode_env_overrides_config(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"DELIVERY_MODE": "telegram"}), encoding="utf-8")
    monkeypatch.setenv("DELIVERY_MODE", "web")
    from config.settings import Settings

    s = Settings(str(cfg))
    assert s.delivery_mode == "web"
    assert s.telegram_enabled is False
