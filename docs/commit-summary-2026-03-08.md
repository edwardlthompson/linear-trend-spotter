# Commit Summary (2026-03-08)

## Scope
- Reworked README to reflect current scanner behavior, configuration, and operations.
- Included all active runtime parameters from `config/settings.py` and `config.json.example`.
- Documented current filter logic and notification payloads.
- Documented CoinGecko retry/backoff and caching behavior now used in production flow.

## Key README Updates
- Corrected setup/config instructions (`config.json.example` -> `config.json`).
- Updated qualification thresholds:
  - Uniformity minimum score is now 55.
  - Gain rules require `7d > 7`, `30d > 30`, and `30d > 7d`.
- Added explicit pipeline stages and operational process overview.
- Added entry/exit notification details including:
  - Total CMC 24h volume in entry alerts.
  - Precise exit reasons in exit alerts.
- Added complete parameter reference table.
- Added operational scripts/cadence and logging outputs.

## Runtime Fixes Included in This Commit
- `database/models.py`: fixed SQL binding mismatch in `add_coin()` that caused scan failure at entry/exit processing.
- `utils/logger.py`: hardened console logging for Windows encoding edge cases to prevent Unicode logging trace floods.
- `api/coingecko.py`: improved retry/backoff/jitter and fail-fast behavior for ticker endpoint.
- `database/cache.py`: added exchange-volume cache table and helpers.
- `main.py`: integrated exchange-volume cache, explicit `30d > 7d` gain rule, precise exit reasons, and updated DB path usage.
- `notifications/formatter.py`: entry includes total CMC 24h volume; exit includes reason text.
- `config/settings.py` and `config.json.example`: default uniformity score threshold updated to 55.
- `processors/gain_filter.py` and `utils/rate_limiter.py`: aligned rule/docs and corrected docstring syntax issues.

## Files
- `README.md`
- `docs/commit-summary-2026-03-08.md`
- `api/coingecko.py`
- `api/coingecko_mapper.py`
- `config.json.example`
- `config/settings.py`
- `database/cache.py`
- `database/models.py`
- `main.py`
- `metrics.json`
- `notifications/formatter.py`
- `processors/gain_filter.py`
- `utils/logger.py`
- `utils/rate_limiter.py`
