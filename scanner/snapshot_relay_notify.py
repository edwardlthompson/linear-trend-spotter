"""Push public snapshot JSON to optional HTTPS relay after worker writes disk copy."""

from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.logger import app_logger

_RELAY_MAX_ATTEMPTS = 6


def _should_retry_http(status: int) -> bool:
    return status in (408, 409, 425, 429, 500, 502, 503, 504)


def maybe_push_qualified_snapshot_relay(data_dir: Path, filename: str) -> None:
    """POST file bytes to relay when QUALIFIED_SNAPSHOT_RELAY_* env vars are set."""
    base = os.getenv("QUALIFIED_SNAPSHOT_RELAY_URL", "").strip().rstrip("/")
    secret = os.getenv("QUALIFIED_SNAPSHOT_RELAY_SECRET", "").strip()
    if not base or not secret:
        return
    path = data_dir / filename
    if not path.is_file():
        app_logger.warning("⚠️ Snapshot relay skipped: missing %s", path)
        return
    try:
        body = path.read_bytes()
    except OSError as e:
        app_logger.warning("⚠️ Snapshot relay read failed: %s", e)
        return

    def _post_once() -> None:
        req = Request(
            f"{base}/internal/ingest-snapshot",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urlopen(req, timeout=120) as resp:
            _ = resp.read()

    sleep_s = 2.0
    last_exc: BaseException | None = None
    for attempt in range(1, _RELAY_MAX_ATTEMPTS + 1):
        try:
            _post_once()
            app_logger.info("📡 Qualified snapshot relay updated")
            return
        except HTTPError as he:
            last_exc = he
            code = int(he.code or 0)
            if _should_retry_http(code) and attempt < _RELAY_MAX_ATTEMPTS:
                app_logger.warning(
                    "⚠️ Snapshot relay HTTP %s (attempt %s/%s); retry in %.0fs",
                    code,
                    attempt,
                    _RELAY_MAX_ATTEMPTS,
                    sleep_s,
                )
                time.sleep(sleep_s)
                sleep_s = min(sleep_s * 2.0, 30.0)
                continue
            app_logger.warning("⚠️ Snapshot relay HTTP %s: %s", code, he.reason)
            return
        except (URLError, OSError, TimeoutError) as net_err:
            last_exc = net_err
            if attempt < _RELAY_MAX_ATTEMPTS:
                app_logger.warning(
                    "⚠️ Snapshot relay transport error (attempt %s/%s): %s; retry in %.0fs",
                    attempt,
                    _RELAY_MAX_ATTEMPTS,
                    net_err,
                    sleep_s,
                )
                time.sleep(sleep_s)
                sleep_s = min(sleep_s * 2.0, 30.0)
                continue
            app_logger.warning("⚠️ Snapshot relay failed: %s", net_err)
            return
        except Exception as ex:
            last_exc = ex
            app_logger.warning("⚠️ Snapshot relay failed: %s", ex)
            return
    if last_exc:
        app_logger.warning("⚠️ Snapshot relay exhausted retries: %s", last_exc)
