from __future__ import annotations

import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.runner import run_backtests_for_final_results
from config.settings import settings


def main() -> int:
    settings._config['BACKTEST_MAX_PARAM_COMBOS'] = 5
    settings._config['BACKTEST_TIMEFRAMES'] = ['1h', '4h']
    settings._config['BACKTEST_MAX_COINS_PER_RUN'] = 3
    settings._config['BACKTEST_PARALLEL_WORKERS'] = 2

    symbols = ['ADA', 'ETH', 'XRP']
    final = [{'symbol': symbol, 'listed_on': ['kraken']} for symbol in symbols]

    start = time.perf_counter()
    summary = run_backtests_for_final_results(final)
    elapsed = time.perf_counter() - start

    baseline = {
        'timestamp': summary['generated_at'],
        'duration_sec': round(elapsed, 2),
        'coins_eligible': summary['coins_eligible'],
        'coins_processed': summary['coins_processed'],
        'coins_failed': summary['coins_failed'],
        'rows_generated': summary['rows_generated'],
        'skipped_count': len(summary['skipped']),
        'timeframes': summary['timeframes'],
        'max_param_combos': settings._config['BACKTEST_MAX_PARAM_COMBOS'],
        'parallel_workers': settings._config['BACKTEST_PARALLEL_WORKERS'],
    }

    out = settings.base_dir / 'docs' / 'backtesting-baseline.json'
    out.write_text(json.dumps(baseline, indent=2), encoding='utf-8')

    print(json.dumps(baseline, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
