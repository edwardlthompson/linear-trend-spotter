from __future__ import annotations

from types import SimpleNamespace

from api.price_history_fallback import PriceHistoryFallbackClient
from utils.provider_circuit import ProviderCallCircuit


class _NoWaitGate:
    def wait(self) -> None:
        return None


class _Session:
    def __init__(self, status_codes: list[int]) -> None:
        self.status_codes = list(status_codes)
        self.calls = 0

    def get(self, url: str, params: dict, timeout: float) -> SimpleNamespace:
        del url, params, timeout
        self.calls += 1
        return SimpleNamespace(status_code=self.status_codes.pop(0))


def test_polygon_symbol_scoped_4xx_does_not_open_provider_circuit() -> None:
    circuit = ProviderCallCircuit("polygon", failure_threshold=2, recovery_timeout=60)
    client = PriceHistoryFallbackClient(
        polygon_api_key="poly-key",
        polygon_rate_gate=_NoWaitGate(),
        polygon_circuit=circuit,
    )
    client.polygon_session = _Session([404, 404, 200])

    assert client._polygon_http_get("https://polygon.example/missing-a", {}, timeout=1, max_retries=1).status_code == 404
    assert client._polygon_http_get("https://polygon.example/missing-b", {}, timeout=1, max_retries=1).status_code == 404

    response = client._polygon_http_get("https://polygon.example/valid", {}, timeout=1, max_retries=1)

    assert response is not None
    assert response.status_code == 200
    assert client.polygon_session.calls == 3
    assert circuit.failures == 0


def test_cmc_symbol_scoped_400_does_not_open_provider_circuit() -> None:
    circuit = ProviderCallCircuit("cmc", failure_threshold=2, recovery_timeout=60)
    client = PriceHistoryFallbackClient(
        cmc_api_key="cmc-key",
        cmc_rate_gate=_NoWaitGate(),
        cmc_circuit=circuit,
    )
    client.cmc_session = _Session([400, 400, 200])

    assert client._cmc_http_get("https://cmc.example/missing-a", {}, timeout=1, max_retries=1).status_code == 400
    assert client._cmc_http_get("https://cmc.example/missing-b", {}, timeout=1, max_retries=1).status_code == 400

    response = client._cmc_http_get("https://cmc.example/valid", {}, timeout=1, max_retries=1)

    assert response is not None
    assert response.status_code == 200
    assert client.cmc_session.calls == 3
    assert circuit.failures == 0


def test_provider_wide_errors_still_open_circuit() -> None:
    circuit = ProviderCallCircuit("polygon", failure_threshold=2, recovery_timeout=60)
    client = PriceHistoryFallbackClient(
        polygon_api_key="poly-key",
        polygon_rate_gate=_NoWaitGate(),
        polygon_circuit=circuit,
    )
    client.polygon_session = _Session([500, 500, 200])

    assert client._polygon_http_get("https://polygon.example/a", {}, timeout=1, max_retries=1).status_code == 500
    assert client._polygon_http_get("https://polygon.example/b", {}, timeout=1, max_retries=1).status_code == 500

    assert client._polygon_http_get("https://polygon.example/skipped", {}, timeout=1, max_retries=1) is None
    assert client.polygon_session.calls == 2
    assert circuit.failures == 2
