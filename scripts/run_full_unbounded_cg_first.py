from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
import main


def run() -> None:
    settings._config['BACKTEST_ENABLED'] = True
    settings._config['BACKTEST_REQUIRE_TARGET_EXCHANGE'] = False
    settings._config['ENTRY_NOTIFICATIONS'] = False
    settings._config['EXIT_NOTIFICATIONS'] = False
    settings._config['NO_CHANGE_NOTIFICATIONS'] = False
    settings._config['BACKTEST_MAX_PARAM_COMBOS'] = 100
    settings._config['BACKTEST_PARALLEL_WORKERS'] = 1
    settings._config['BACKTEST_MAX_COINS_PER_RUN'] = 0
    main.run_scanner()


if __name__ == '__main__':
    run()
