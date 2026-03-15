from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
import main


def run() -> None:
    for artifact_name in [
        "backtest_results.json",
        "backtest_checkpoint.json",
        "backtest_telemetry.jsonl",
    ]:
        artifact_path = ROOT / artifact_name
        if artifact_path.exists():
            artifact_path.unlink()

    settings._config["BACKTEST_RESUME_ENABLED"] = False
    settings._config["BACKTEST_PER_COIN_TIMEOUT_SECONDS"] = 5400
    main.run_scanner()


if __name__ == "__main__":
    run()
