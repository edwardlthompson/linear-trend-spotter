# Commit Summary (2026-03-12 Insights Layer)

## Scope

- Implemented a new scan insights layer spanning ranking persistence, early warnings, watchlist generation, drift detection, outcome analytics, portfolio simulation, and reliability scoring.
- Added hourly summary image support and backtest confidence weighting.
- Updated README to document new scanner behavior and artifacts.

## Why This Change

- The scanner already had strong entry/exit logic, but lacked operational context for what was weakening, recurring, drifting, or performing after alerts.
- A full database migration for every requested feature would be unnecessarily invasive for this scope.
- This change intentionally uses a consolidated artifact-backed insights layer (`scanner_insights.json`) for most persistence because it reduces schema churn while still providing durable outputs for dashboards and later expansion.

## Implemented Features

- **Rank persistence dashboard**
  - Stores rolling rank snapshots and top movers.
- **Exit early-warning alerts**
  - Warns on active coins nearing exit based on gain/volume/uniformity/rank/health deterioration.
- **Active coin health score**
  - Combines rank, uniformity, ATR, exchange quality, reliability, volume acceleration, and backtest confidence.
- **Re-entry quality logic**
  - Scores symbols by recent exit churn to distinguish fresh entries from recycled re-entries.
- **Backtest confidence weighting**
  - Re-ranks strategy rows by a weighted score instead of raw net return alone.
- **Hourly summary image**
  - Renders a compact dashboard image for active rankings and watchlist rows.
- **Benchmark drift monitor**
  - Compares current scan shape versus rolling historical medians.
- **Exchange-quality filter**
  - Adds final-stage filtering based on exchange breadth and liquidity concentration quality.
- **Watchlist mode**
  - Captures near-qualifiers that narrowly miss final inclusion.
- **Regime detection**
  - Classifies the current scan into `trend-friendly`, `constructive`, `mixed`, or `risk-off`.
- **Post-alert outcome analytics**
  - Tracks active alert P&L distributions and recent exit samples.
- **Data-source reliability scoring**
  - Scores symbols by mapping/ticker/OHLCV source quality.
- **Portfolio simulation mode**
  - Maintains a lightweight alert-following portfolio state with positions, cash, equity, and trade log.

## Main Code Changes

- `utils/insights.py`
  - New shared analytics/persistence module for dashboarding and monitoring outputs.
- `main.py`
  - Integrated exchange-quality filtering, health scoring, regime detection, watchlist creation, early-warning generation, insights persistence, and hourly summary image sending.
- `notifications/formatter.py`
  - Entry notifications now include health/exchange-quality/reliability/re-entry/backtest-confidence context.
  - Added formatter helpers for warnings, watchlist, drift, and summary image captioning.
- `notifications/image_renderer.py`
  - Added hourly summary dashboard image renderer.
- `backtesting/report.py`
  - Added confidence-aware strategy ordering for notification rows.
- `config/settings.py`
  - Added settings for exchange-quality filter, watchlist, early warnings, hourly summary image, portfolio simulation, and scanner insights artifact.

## Documentation Changes

- `README.md`
  - Added feature descriptions for early warnings, watchlist, hourly dashboard image, and scanner insights artifact.
  - Documented the new health/risk/reliability-related notification fields.

## Files

- `main.py`
- `config/settings.py`
- `backtesting/report.py`
- `notifications/formatter.py`
- `notifications/image_renderer.py`
- `utils/insights.py`
- `README.md`
- `docs/commit-summary-2026-03-12-insights.md`
