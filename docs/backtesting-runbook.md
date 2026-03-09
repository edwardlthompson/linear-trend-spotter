# Backtesting Runbook

- **Scope:** Sprint 4.2 operational run/fix guidance for integrated backtesting.
- **Output artifact:** `backtest_results.json`

## Quick Start

1. Enable backtesting in `config.json`:
   - `BACKTEST_ENABLED: true`
   - `BACKTEST_REQUIRE_TARGET_EXCHANGE: false` (default; includes all final-phase coins)
   - Optional gate mode: set `BACKTEST_REQUIRE_TARGET_EXCHANGE: true` and choose `BACKTEST_EXCHANGES`
2. Run scanner:
   - `python main.py`
3. Render final backtesting report:
   - `python scripts/render_backtest_report.py`

## Verification Checklist

- [ ] Scanner completes (even if some coin-level backtests fail).
- [ ] `backtest_results.json` is generated.
- [ ] `exchange_gate_enabled` in artifact matches intended mode.
- [ ] Artifact has non-empty `results` list.
- [ ] `scripts/render_backtest_report.py` outputs ranked table.
- [ ] Output includes `B&H` rows.
- [ ] Output includes `#1 Settings:` line with full parameter details.

## Recovery / Failure Policy

### 1) API/data issues

Symptoms:

- Many entries in `skipped` with load/fetch reasons.

Actions:

- Reduce scope for recovery run:
  - Lower `BACKTEST_MAX_COINS_PER_RUN`.
  - Restrict `BACKTEST_TIMEFRAMES` to `['1h']` temporarily.
- Rerun and verify artifact generation.

### 2) Runtime pressure

Symptoms:

- Slow runs or process timeouts.

Actions:

- Reduce `BACKTEST_MAX_PARAM_COMBOS`.
- Reduce `BACKTEST_PARALLEL_WORKERS`.
- Keep trailing-stop sweep unchanged (required contract), but cut combo volume.

### 3) Partial worker failures

Symptoms:

- Non-zero `coins_failed` in artifact summary.

Actions:

- Confirm scanner still completed (expected behavior by design).
- Inspect `failures` in `backtest_results.json`.
- Re-run targeted symbol checks via constrained smoke command.

## Known Constraints

- First full integrated scan can be long due to external API calls and per-indicator optimization loops.
- `B&H` is included for comparison in report rows and does not use trailing stops.
- Report output is ranked by net % descending.
- Data source behavior is modular by availability:
   - Primary source for all symbols: CoinGecko hourly/daily OHLCV.
   - Intraday fallback when CoinGecko hourly is unavailable: Polygon `1h` OHLCV.
   - Last-resort fallback: CoinGecko `1d` OHLC (strategy rows for `1d` only).

## Baseline Snapshot (Controlled)

- **Date (UTC):** 2026-03-09T02:04:27.287322+00:00
- **Run profile:** `3` Kraken symbols, timeframes `1h + 4h`, `max_param_combos=5`, `parallel_workers=2`
- **Duration:** `80.8s`
- **Eligible coins:** `3`
- **Processed coins:** `3`
- **Failed coins:** `0`
- **Rows generated:** `78`
- **Skipped count:** `0`

Baseline artifact:

- `docs/backtesting-baseline.json`
