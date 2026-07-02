"""Tests for Render-provisioned ntfy environment settings."""

from __future__ import annotations

from config.settings import Settings


def test_ntfy_env_overrides_enable_and_public_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NTFY_ENABLED", "true")
    monkeypatch.setenv("NTFY_BASE_URL", "https://ntfy.example")
    monkeypatch.setenv("NTFY_TOPIC", "topic-env")
    monkeypatch.setenv("NTFY_TOKEN", "token-env")
    monkeypatch.setenv("NTFY_PRIORITY", "high")
    monkeypatch.setenv("NTFY_DASHBOARD_URL", "https://example.com/dashboard")

    cfg = Settings(config_path=str(tmp_path / "missing.json"))

    assert cfg.ntfy_enabled is True
    assert cfg.ntfy_base_url == "https://ntfy.example"
    assert cfg.ntfy_topic == "topic-env"
    assert cfg.ntfy_token == "token-env"
    assert cfg.ntfy_priority == "high"
    assert cfg.ntfy_dashboard_url == "https://example.com/dashboard"
    assert cfg.ntfy_public_subscribe_url == "https://ntfy.example/topic-env"


def test_ntfy_enabled_false_env_is_not_truthy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NTFY_ENABLED", "false")
    monkeypatch.setenv("NTFY_TOPIC", "topic-env")

    cfg = Settings(config_path=str(tmp_path / "missing.json"))

    assert cfg.ntfy_enabled is False
    assert cfg.ntfy_public_subscribe_url == ""
