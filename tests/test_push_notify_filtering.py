"""Push relay per-subscriber exchange filtering."""

from push_server.notify_filtering import (
    coin_matches_notify_exchanges,
    filter_events_for_subscriber,
    format_change_body,
    normalize_notify_exchange_ids,
)


def test_normalize_notify_exchange_ids():
    assert normalize_notify_exchange_ids(["Kraken", "kraken", ""]) == ["kraken"]
    assert normalize_notify_exchange_ids(None) == []


def test_kraken_subscriber_skips_mexc_only_entry():
    entered = [{"symbol": "ZAP", "listed_on": ["mexc"]}]
    ent_f, ext_f = filter_events_for_subscriber(["kraken"], entered, [])
    assert ent_f == []
    assert ext_f == []


def test_kraken_subscriber_gets_dual_listed_entry():
    entered = [{"symbol": "ZAP", "listed_on": ["mexc", "kraken"]}]
    ent_f, ext_f = filter_events_for_subscriber(["kraken"], entered, [])
    assert len(ent_f) == 1
    assert ent_f[0]["symbol"] == "ZAP"


def test_empty_notify_prefs_matches_all():
    ent_f, ext_f = filter_events_for_subscriber(
        [],
        [{"symbol": "A", "listed_on": ["mexc"]}],
        [{"symbol": "B", "listed_on": []}],
    )
    assert len(ent_f) == 1
    assert len(ext_f) == 1


def test_coin_missing_listing_not_matched_when_filter_set():
    assert not coin_matches_notify_exchanges({"symbol": "X", "listed_on": []}, ["kraken"])


def test_format_change_body():
    body = format_change_body(
        [{"symbol": "ADA", "listed_on": ["kraken"]}],
        [{"symbol": "SOL", "listed_on": ["mexc"]}],
    )
    assert "ADA" in body and "SOL" in body
