from __future__ import annotations

import json
import os
import random
import traceback
import time
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Any

import requests


def log_progress(message: str) -> None:
    with open('benchmark_40_tuned_progress.log', 'a', encoding='utf-8') as progress:
        progress.write(f"{time.strftime('%H:%M:%S')} {message}\n")


@dataclass
class Scenario:
    name: str
    batch_size: int
    timeout_seconds: int
    tuned: bool = False


LAST_CALL_TS: dict[str, float] = {}

PROVIDER_MIN_INTERVAL: dict[str, float] = {
    'coingecko': 3.0,
    'coinmarketcap': 1.5,
    'coinlore': 1.0,
    'polygon': 2.5,
}


COINGECKO_FALLBACK_IDS: dict[str, str] = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'USDT': 'tether',
    'BNB': 'binancecoin',
    'XRP': 'ripple',
    'USDC': 'usd-coin',
    'SOL': 'solana',
    'TRX': 'tron',
    'DOGE': 'dogecoin',
    'ADA': 'cardano',
    'BCH': 'bitcoin-cash',
    'XMR': 'monero',
    'LINK': 'chainlink',
    'DAI': 'dai',
    'XLM': 'stellar',
    'HBAR': 'hedera-hashgraph',
    'LTC': 'litecoin',
    'AVAX': 'avalanche-2',
    'TON': 'the-open-network',
    'SHIB': 'shiba-inu',
    'CRO': 'crypto-com-chain',
    'PAXG': 'pax-gold',
    'DOT': 'polkadot',
    'UNI': 'uniswap',
    'MNT': 'mantle',
    'OKB': 'okb',
    'TAO': 'bittensor',
    'ETC': 'ethereum-classic',
    'APT': 'aptos',
    'NEAR': 'near',
    'ATOM': 'cosmos',
    'FIL': 'filecoin',
    'ARB': 'arbitrum',
    'OP': 'optimism',
    'AAVE': 'aave',
    'ALGO': 'algorand',
    'VET': 'vechain',
    'ICP': 'internet-computer',
    'INJ': 'injective-protocol',
    'SUI': 'sui',
}


def load_env(path: str = '.env') -> None:
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())


def request_json(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 12,
    provider: str = 'generic',
    max_retries: int = 8,
) -> tuple[int, Any, float]:
    total_latency = 0.0
    last_status = 0
    last_body: Any = {}

    for attempt in range(max_retries):
        min_interval = PROVIDER_MIN_INTERVAL.get(provider, 0.5)
        last_call = LAST_CALL_TS.get(provider, 0.0)
        wait_needed = min_interval - (time.time() - last_call)
        if wait_needed > 0:
            time.sleep(wait_needed)

        start = time.perf_counter()
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout_seconds)
            latency_ms = (time.perf_counter() - start) * 1000
            LAST_CALL_TS[provider] = time.time()
            total_latency += latency_ms

            try:
                body = response.json()
            except Exception:
                body = {'_raw': response.text[:300]}

            status = response.status_code
            last_status = status
            last_body = body

            if status == 200:
                return status, body, total_latency

            if status == 429 and attempt < max_retries - 1:
                retry_after = response.headers.get('Retry-After')
                if retry_after and retry_after.isdigit():
                    sleep_seconds = min(max(1, int(retry_after)), 45)
                else:
                    sleep_seconds = min(4 + (attempt * 3), 45) + random.uniform(0, 1.2)
                time.sleep(sleep_seconds)
                continue

            if status in (408, 500, 503) and attempt < max_retries - 1:
                sleep_seconds = min(2 + (attempt * 2), 20) + random.uniform(0, 0.8)
                time.sleep(sleep_seconds)
                continue

            return status, body, total_latency
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            LAST_CALL_TS[provider] = time.time()
            total_latency += latency_ms
            last_status = 0
            last_body = {'error': str(exc)}
            if attempt < max_retries - 1:
                time.sleep(min(2 + (attempt * 2), 20) + random.uniform(0, 0.8))
                continue

    return last_status, last_body, total_latency


def build_maps(session: requests.Session) -> dict[str, dict[str, str]]:
    maps = {'coingecko': {}, 'polygon': {}}

    st, body, _ = request_json(session, 'https://api.coingecko.com/api/v3/coins/list', params={'include_platform': 'false'}, timeout_seconds=20, provider='coingecko', max_retries=10)
    if st == 200 and isinstance(body, list):
        for x in body:
            sym = str(x.get('symbol', '')).upper()
            cid = str(x.get('id', ''))
            if sym and cid and sym not in maps['coingecko']:
                maps['coingecko'][sym] = cid

    if not maps['coingecko']:
        st, body, _ = request_json(
            session,
            'https://api.coingecko.com/api/v3/coins/markets',
            params={'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 250, 'page': 1, 'sparkline': 'false'},
            timeout_seconds=20,
            provider='coingecko',
            max_retries=10,
        )
        if st == 200 and isinstance(body, list):
            for x in body:
                sym = str(x.get('symbol', '')).upper()
                cid = str(x.get('id', ''))
                if sym and cid and sym not in maps['coingecko']:
                    maps['coingecko'][sym] = cid

    polygon_key = os.getenv('POLYGON_API_KEY', '')
    if polygon_key:
        st, body, _ = request_json(session, 'https://api.polygon.io/v3/reference/tickers', params={'market': 'crypto', 'active': 'true', 'limit': 1000, 'apiKey': polygon_key}, timeout_seconds=20, provider='polygon', max_retries=10)
        if st == 200 and isinstance(body, dict):
            for x in body.get('results', []):
                base = str(x.get('base_currency_symbol', '')).upper()
                quote = str(x.get('currency_symbol', '')).upper()
                ticker = str(x.get('ticker', ''))
                if base and quote == 'USD' and ticker and base not in maps['polygon']:
                    maps['polygon'][base] = ticker

    return maps


def choose_40_symbols(maps: dict[str, dict[str, str]]) -> list[str]:
    seed = [
        'BTC','ETH','USDT','BNB','XRP','USDC','SOL','TRX','DOGE','ADA',
        'BCH','XMR','LINK','DAI','XLM','HBAR','LTC','AVAX','TON','SHIB',
        'CRO','PAXG','DOT','UNI','MNT','OKB','TAO','ETC','APT','NEAR',
        'ATOM','FIL','ARB','OP','AAVE','ALGO','VET','ICP','INJ','SUI'
    ]
    shared = [s for s in seed if s in maps['coingecko'] and s in maps['polygon']]
    return shared[:40] if len(shared) >= 40 else seed[:40]


def run_history(session: requests.Session, provider: str, symbols: list[str], symbol_map: dict[str, str], scenario: Scenario) -> dict[str, Any]:
    today = date.today()
    start_30d = today - timedelta(days=30)
    def resolve_symbol(sym: str) -> str | None:
        if sym in symbol_map:
            return symbol_map[sym]
        if provider == 'coingecko':
            return COINGECKO_FALLBACK_IDS.get(sym)
        return None

    resolved_pairs = [(s, resolve_symbol(s)) for s in symbols]
    resolved_pairs = [(s, ident) for s, ident in resolved_pairs if ident][:40]

    t0 = time.perf_counter()
    statuses: list[int] = []
    latencies: list[float] = []
    success = 0

    if provider == 'coingecko':
        ids = [ident for _, ident in resolved_pairs]
        st, body, lat = request_json(
            session,
            'https://api.coingecko.com/api/v3/coins/markets',
            params={
                'vs_currency': 'usd',
                'ids': ','.join(ids),
                'sparkline': 'false',
                'price_change_percentage': '30d',
            },
            timeout_seconds=scenario.timeout_seconds,
            provider='coingecko',
            max_retries=10,
        )
        statuses.append(st)
        latencies.append(round(lat, 2))
        if st == 200 and isinstance(body, list):
            success = min(len(body), len(resolved_pairs))

    elif provider == 'polygon':
        st, body, lat = request_json(
            session,
            f'https://api.polygon.io/v2/aggs/grouped/locale/global/market/crypto/{today.isoformat()}',
            params={'adjusted': 'true', 'apiKey': os.getenv('POLYGON_API_KEY', '')},
            timeout_seconds=scenario.timeout_seconds,
            provider='polygon',
            max_retries=12,
        )
        statuses.append(st)
        latencies.append(round(lat, 2))
        if st == 200 and isinstance(body, dict):
            available = {
                str(item.get('T', '')) for item in body.get('results', [])
            }
            expected = {
                ident for _, ident in resolved_pairs
            }
            success = len(expected & available)

    total_ms = (time.perf_counter() - t0) * 1000
    return {
        'provider': provider,
        'scenario': scenario.name,
        'coins_target': len(symbols),
        'coins_resolved': len(resolved_pairs),
        'coins_success': success,
        'success_ratio': round(success / len(resolved_pairs), 3) if resolved_pairs else 0.0,
        'status_codes_seen': sorted(set(statuses)),
        'total_ms': round(total_ms, 2),
        'median_request_ms': round(median(latencies), 2) if latencies else None,
        'batch_size': scenario.batch_size,
        'effective_batch_size': 1,
        'timeout_seconds': scenario.timeout_seconds,
        'provider_tuning': scenario.tuned,
    }


def run_snapshot_40(session: requests.Session, symbols: list[str]) -> list[dict[str, Any]]:
    rows = []
    csv40 = ','.join(symbols)

    calls = [
        ('CoinGecko', 'https://api.coingecko.com/api/v3/coins/markets', {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 250, 'page': 1, 'sparkline': 'false'}, {}),
        ('CoinMarketCap', 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest', {'symbol': csv40, 'convert': 'USD'}, {'X-CMC_PRO_API_KEY': os.getenv('CMC_API_KEY', ''), 'Accept': 'application/json'}),
        ('CoinLore', 'https://api.coinlore.net/api/tickers/', {'start': 0, 'limit': 100}, {}),
        ('Polygon', 'https://api.polygon.io/v3/reference/tickers', {'market': 'crypto', 'active': 'true', 'limit': 1000, 'apiKey': os.getenv('POLYGON_API_KEY', '')}, {}),
    ]

    for name, url, params, headers in calls:
        provider_name = 'generic'
        if name == 'CoinGecko':
            provider_name = 'coingecko'
        elif name == 'CoinMarketCap':
            provider_name = 'coinmarketcap'
        elif name == 'CoinLore':
            provider_name = 'coinlore'
        elif name == 'Polygon':
            provider_name = 'polygon'

        st, body, lat = request_json(
            session,
            url,
            params=params,
            headers=headers,
            timeout_seconds=15,
            provider=provider_name,
            max_retries=8,
        )
        if name == 'CoinGecko':
            count = len(body) if isinstance(body, list) else 0
        elif name == 'CoinMarketCap':
            count = len(body.get('data', {})) if isinstance(body, dict) else 0
        elif name == 'CoinLore':
            count = len(body.get('data', [])) if isinstance(body, dict) else 0
        else:
            count = len(body.get('results', [])) if isinstance(body, dict) else 0
        rows.append({'source': name, 'status_code': st, 'latency_ms': round(lat, 2), 'records_returned': count, 'covers_40': count >= 40})

    return rows


def main() -> None:
    with open('benchmark_40_tuned_progress.log', 'w', encoding='utf-8') as progress:
        progress.write('start\n')

    load_env()
    log_progress('env_loaded')
    session = requests.Session()
    session.headers.update({'User-Agent': 'linear-trend-spotter-benchmark/1.0'})
    log_progress('session_ready')

    maps = build_maps(session)
    log_progress(f"maps_built coingecko={len(maps.get('coingecko', {}))} polygon={len(maps.get('polygon', {}))}")
    symbols = choose_40_symbols(maps)
    log_progress(f"symbols_selected count={len(symbols)}")

    scenarios = [
        Scenario('reliability_timeout15', 1, 15, True),
    ]

    history = []
    for sc in scenarios:
        for provider in ('coingecko', 'polygon'):
            log_progress(f"history_start provider={provider} scenario={sc.name}")
            history.append(run_history(session, provider, symbols, maps.get(provider, {}), sc))
            log_progress(f"history_done provider={provider} scenario={sc.name}")

    log_progress('snapshot_start')
    out = {
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'symbols_40': symbols,
        'snapshot_bulk_40': run_snapshot_40(session, symbols),
        'history_40_simulation': history,
    }
    log_progress('snapshot_done')

    with open('benchmark_40_tuned_results.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    log_progress('results_written')

    print(json.dumps({'generated_at_utc': out['generated_at_utc'], 'rows': len(out['history_40_simulation'])}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        with open('benchmark_40_tuned_error.txt', 'w', encoding='utf-8') as err:
            err.write(traceback.format_exc())
        raise
