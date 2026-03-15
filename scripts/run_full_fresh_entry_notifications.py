from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from database.models import ActiveCoinsDatabase
import main


def run() -> None:
    active_db = ActiveCoinsDatabase(settings.db_paths["scanner"])
    active_db.execute("DELETE FROM active_coins")
    active_db.execute("DELETE FROM cooldown_exits")

    for artifact in (
        settings.base_dir / "backtest_checkpoint.json",
        settings.base_dir / "backtest_results.json",
        settings.base_dir / "backtest_telemetry.jsonl",
    ):
        try:
            if artifact.exists():
                artifact.unlink()
        except Exception:
            pass

    settings._config["ENTRY_NOTIFICATIONS"] = True
    settings._config["EXIT_NOTIFICATIONS"] = True
    settings._config["NO_CHANGE_NOTIFICATIONS"] = False
    settings._config["BACKTEST_RESUME_ENABLED"] = False
    settings._config["BACKTEST_PER_COIN_TIMEOUT_SECONDS"] = max(
        int(settings._config.get("BACKTEST_PER_COIN_TIMEOUT_SECONDS", 5400)),
        5400,
    )

    main.run_scanner()


if __name__ == "__main__":
    run()
