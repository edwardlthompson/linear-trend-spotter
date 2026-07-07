"""Tests for Tier-C ntfy notify hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scanner import ntfy_notify


def _cfg(monkeypatch, **kwargs: object) -> None:
    for key, val in kwargs.items():
        monkeypatch.setitem(ntfy_notify.settings._config, key, val)


def test_ntfy_skipped_when_disabled(monkeypatch) -> None:
    _cfg(monkeypatch, NTFY_ENABLED=False)
    with patch.object(ntfy_notify, "urlopen") as mock_open:
        ntfy_notify.maybe_notify_ntfy_qualified_changes([{"symbol": "BTC"}], None)
        mock_open.assert_not_called()


def test_ntfy_skipped_when_no_topic(monkeypatch) -> None:
    _cfg(monkeypatch, NTFY_ENABLED=True, NTFY_BASE_URL="https://ntfy.sh", NTFY_TOPIC="")
    with patch.object(ntfy_notify, "urlopen") as mock_open:
        ntfy_notify.maybe_notify_ntfy_qualified_changes([{"symbol": "BTC"}], None)
        mock_open.assert_not_called()


def test_ntfy_posts_when_enabled(monkeypatch) -> None:
    _cfg(
        monkeypatch,
        NTFY_ENABLED=True,
        NTFY_BASE_URL="https://ntfy.sh",
        NTFY_TOPIC="secret-topic",
        NTFY_TOKEN="tk_test",
        NTFY_PRIORITY="default",
        NTFY_DASHBOARD_URL="https://example.com/dash",
    )
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"ok"
    with patch.object(ntfy_notify, "urlopen", return_value=mock_resp) as mock_open:
        ntfy_notify.maybe_notify_ntfy_qualified_changes(
            [{"symbol": "BTC", "listed_on": ["coinbase"]}],
            None,
        )
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://ntfy.sh/secret-topic"
        assert req.headers["Authorization"] == "Bearer tk_test"
        assert req.headers["Click"] == "https://example.com/dash"


def test_ntfy_settings_read_environment_overrides(monkeypatch) -> None:
    _cfg(
        monkeypatch,
        NTFY_ENABLED=False,
        NTFY_BASE_URL="https://config.example",
        NTFY_TOPIC="config-topic",
        NTFY_TOKEN="config-token",
        NTFY_PRIORITY="default",
        NTFY_DASHBOARD_URL="https://config.example/dash",
    )
    monkeypatch.setenv("NTFY_ENABLED", "true")
    monkeypatch.setenv("NTFY_BASE_URL", "https://ntfy.example")
    monkeypatch.setenv("NTFY_TOPIC", "env-topic")
    monkeypatch.setenv("NTFY_TOKEN", "env-token")
    monkeypatch.setenv("NTFY_PRIORITY", "high")
    monkeypatch.setenv("NTFY_DASHBOARD_URL", "https://env.example/dash")

    assert ntfy_notify.settings.ntfy_enabled is True
    assert ntfy_notify.settings.ntfy_base_url == "https://ntfy.example"
    assert ntfy_notify.settings.ntfy_topic == "env-topic"
    assert ntfy_notify.settings.ntfy_token == "env-token"
    assert ntfy_notify.settings.ntfy_priority == "high"
    assert ntfy_notify.settings.ntfy_dashboard_url == "https://env.example/dash"


def test_ntfy_no_op_without_entry_exit(monkeypatch) -> None:
    _cfg(monkeypatch, NTFY_ENABLED=True, NTFY_TOPIC="t")
    with patch.object(ntfy_notify, "urlopen") as mock_open:
        ntfy_notify.maybe_notify_ntfy_qualified_changes([], [])
        mock_open.assert_not_called()
