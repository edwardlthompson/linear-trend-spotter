# Linear Trend Spotter — Backtesting Implementation Plan

<!-- markdownlint-disable MD024 MD060 -->

- **Project:** `linear-trend-spotter`
- **Plan Type:** Incremental Build Plan (Milestones + Sprints)
- **Date:** 2026-03-08
- **Status:** READY
- **Audience:** AI-first, Human-second
- **Execution Mode:** In-program compute (no LLM/agent for numeric backtest execution)

---

## Overview

This plan defines a dependency-ordered, low-risk implementation path for adding backtesting to the existing scanner without overwhelming the VS Code coding agent context window. The sequence is designed for **error-free environment first**, then **data model correctness**, then **strategy correctness**, then **pipeline integration and performance hardening**.

The work is split into **4 milestones** with **2 sprints each** (8 total sprints). Each sprint is intentionally scoped so it can be executed in one agent session with a tight run/fix/verify loop.

### Explicit Deviation from Prior Logic (Intentional)

- The current pipeline stores a 30-day close-price series in `price_cache` for uniformity scoring.
- Backtesting requirements need **1h/4h/daily**, plus indicators that require **OHLCV** (especially MFI).
- Therefore, this plan intentionally deviates from prior logic by introducing OHLCV-based historical storage and local timeframe resampling.
- **Why:** Reusing close-only daily data would produce invalid or incomplete backtest results and block most required indicators.

### Guiding Constraints

| Constraint | Strategy |
|------------|----------|
| Keep scanner stable | Backtesting is feature-flagged and initially isolated from normal scan flow. |
| Avoid agent overload | Each sprint has strict scope, explicit deliverables, and copy/paste prompt. |
| Minimize runtime errors | Build order starts with env, dependency checks, and smoke tests before heavy logic. |
| Deterministic results | Numeric backtesting runs in Python only (pandas/vectorbt/TA), no LLM in execution loop. |
| Future exchange expansion | Kraken-first gating implemented as a generic exchange filter abstraction. |

### Milestone Dependency Chain

```text
Milestone 1: Environment + Data Foundation
    Sprint 1.1 -> Sprint 1.2
    provides: stable Python env, dependency gates, OHLCV schema/cache, integrity checks
    ↓
Milestone 2: Core Engine + Initial Indicators
    Sprint 2.1 -> Sprint 2.2
    provides: deterministic backtest engine, fees/capital rules, baseline output format
    ↓
Milestone 3: Full Strategy + Optimization Surface
    Sprint 3.1 -> Sprint 3.2
    provides: all required indicators, grid-search + trailing stop optimization
    ↓
Milestone 4: Scanner Integration + Parallel Runs + Reliability
    Sprint 4.1 -> Sprint 4.2
    provides: run on final-stage Kraken coins, ranked outputs, production guardrails
    ↓
Backtesting Capability Complete (requirements-compliant)
```

---

## Current Backtesting Readiness Assessment

| Area | Current State | Gap |
|------|---------------|-----|
| Final-stage candidate list | Available in `main.py` (`final_results`) | Needs backtest hook after final qualification |
| Exchange filtering | `listed_on` exists | Need Kraken-only execution gate (configurable for future exchanges) |
| Historical data | 30-day daily close series cached | Need 30-day 1h OHLCV source + resampled 4h/daily |
| Backtest engine | Not present | Need deterministic long-only engine with fees + trailing stop |
| Optimization | Not present | Need bounded parameter grid (50–100 combos max/indicator/TF) |
| Output artifacts | Existing scan logs/results only | Need ranked table + exact #1 settings output |

---

## Milestone 1 — Environment + Data Foundation

**Goal:** eliminate setup uncertainty, then establish correct OHLCV data model and retrieval so every later sprint runs on valid inputs.

---

### Sprint 1.1 — Environment Lock + Dependency Validation

**Goal:** create a reproducible Python environment and dependency verification script before implementing any backtest logic.

#### Deliverables

| File | Change |
|------|--------|
| `requirements.txt` | Add `pandas`, `numpy`, `vectorbt`, `TA-Lib` (or fallback strategy noted), `tabulate` |
| `config/settings.py` + `config.json.example` | Add backtesting feature flags and limits |
| `scripts/verify_backtest_env.py` | New smoke-check script for imports, versions, and minimal vectorized run |
| `docs/backtesting-env-notes.md` | Install notes + TA-Lib fallback instructions |

#### Steps

1. Add backtesting settings keys (all default-safe/off):
   - `BACKTEST_ENABLED=false`
   - `BACKTEST_EXCHANGES=['kraken']`
   - `BACKTEST_STARTING_CAPITAL=1000`
   - `BACKTEST_FEE_BPS_ROUND_TRIP=52`
   - `BACKTEST_MAX_PARAM_COMBOS=100`
   - `BACKTEST_PARALLEL_WORKERS` (bounded)
2. Install packages and run `scripts/verify_backtest_env.py`.
3. If TA-Lib wheel fails on host, keep architecture with pluggable indicator backend and document fallback path.

#### Error Correction Protocol

- If import failures occur, do **not** continue to strategy code.
- Fix environment first; rerun smoke check until pass.
- Record exact package/version in `docs/backtesting-env-notes.md`.

#### Exit Criteria

- [ ] Env verification script exits 0.
- [ ] Backtesting config keys exist and load successfully.
- [ ] Feature remains disabled by default.

#### Copy/Paste Prompt (Sprint 1.1)

```markdown
Implement Sprint 1.1 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Add backtesting config keys to `config/settings.py` + `config.json.example`.
2) Update `requirements.txt` with backtesting deps.
3) Create `scripts/verify_backtest_env.py` and run it.
4) Create `docs/backtesting-env-notes.md` with exact install/runtime notes.
Do not implement engine/indicators yet.
Run/fix until env smoke test passes.
```

---

### Sprint 1.2 — OHLCV Storage + Data Access Layer

**Goal:** implement 30-day OHLCV retrieval and cache persistence, including exchange-aware metadata.

#### Deliverables

| File | Change |
|------|--------|
| `database/cache.py` | Add OHLCV cache table(s) and access methods |
| `api/` module(s) | Add/reuse fetch path for hourly OHLCV history |
| `backtesting/data_loader.py` | New: normalize OHLCV and resample to 4h/daily |
| `scripts/verify_backtest_data.py` | New: validates OHLCV completeness per coin |

#### Steps

1. Add schema for OHLCV candles keyed by `coin_id`, timeframe base, timestamp.
2. Store source, fetch timestamp, and row count for validation.
3. Implement loader returning standardized DataFrame with columns: `open, high, low, close, volume`.
4. Resample 1h -> 4h/daily locally to avoid extra API calls.
5. Add integrity checks: missing bars, non-monotonic timestamps, non-positive prices.

#### Error Correction Protocol

- Reject incomplete OHLCV series before engine stage.
- If data source is partial, mark coin as skipped with explicit reason.
- Never silently backfill with close-only data.

#### Exit Criteria

- [ ] 1h OHLCV available for target test coins.
- [ ] 4h/daily resamples reproducible from same base 1h data.
- [ ] Data verifier script passes for at least 10 Kraken-listed symbols.

#### Copy/Paste Prompt (Sprint 1.2)

```markdown
Implement Sprint 1.2 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Add OHLCV cache schema/methods in `database/cache.py`.
2) Implement `backtesting/data_loader.py` with 1h base + 4h/daily resampling.
3) Add `scripts/verify_backtest_data.py` and run it on at least 10 Kraken symbols.
4) Add explicit skip reasons for incomplete data.
Do not implement indicators/optimization yet.
```

---

## Milestone 2 — Core Engine + Initial Indicators

**Goal:** build deterministic trade simulation correctness before scaling to all indicators.

---

### Sprint 2.1 — Backtest Engine Core (Long-Only, Fees, Trailing Stop)

**Goal:** implement the execution kernel and portfolio accounting rules exactly once.

#### Deliverables

| File | Change |
|------|--------|
| `backtesting/engine.py` | Core simulation: entries on buy, exits on stop/sell, long-only |
| `backtesting/models.py` | Dataclasses/types for trades/results/settings |
| `scripts/verify_backtest_engine.py` | Deterministic unit-style checks on synthetic candles |

#### Steps

1. Implement rules:
   - Start capital = $1000.
   - Long-only, no leverage.
   - Round-trip taker fee = 0.52% (Kraken default).
   - Enter only on buy signals.
   - If trailing stop hits: exit and wait until next buy signal.
2. Add B&H benchmark calculator.
3. Return metrics: final $, net %, trades, win %.

#### Error Correction Protocol

- Use synthetic controlled datasets to verify fee math and stop behavior.
- If metrics differ between runs for same input, block promotion to next sprint.

#### Exit Criteria

- [ ] Engine deterministic on repeated runs.
- [ ] Trailing stop behavior validated with synthetic tests.
- [ ] B&H result generated from same OHLCV input.

#### Copy/Paste Prompt (Sprint 2.1)

```markdown
Implement Sprint 2.1 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Create `backtesting/models.py` and `backtesting/engine.py`.
2) Implement exact trade rules (long-only, $1000, 0.52% round-trip fee, trailing stop behavior).
3) Add `scripts/verify_backtest_engine.py` with deterministic checks.
4) Add B&H baseline calculation.
Do not add broad indicator set yet.
```

---

### Sprint 2.2 — Signal Layer v1 + Ranked Report Skeleton

**Goal:** wire initial indicators (RSI, EMA crossover, SMA crossover) end-to-end to validate full result path.

#### Deliverables

| File | Change |
|------|--------|
| `backtesting/signals.py` | Signal generation for first 3 indicators |
| `backtesting/report.py` | Ranked table formatting + B&H row |
| `run_backtests.py` | CLI entrypoint for standalone test runs |

#### Steps

1. Implement signal conventions (buy/sell) for RSI, EMA cross, SMA cross.
2. Run across 1h/4h/daily with fixed starter params.
3. Produce required output table format:
   `| Indicator | TF | Key Settings | Stop Loss % | Final $ | Net % | Trades | Win % |`
4. Include B&H row in same ranking output.

#### Error Correction Protocol

- Validate that every table row maps to a concrete result object.
- Fail fast on NaN metrics or empty trades without explicit reason.

#### Exit Criteria

- [ ] CLI run generates valid ranked table including B&H.
- [ ] Initial indicators run on all 3 timeframes.
- [ ] Output is stable and parseable for next milestones.

#### Copy/Paste Prompt (Sprint 2.2)

```markdown
Implement Sprint 2.2 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Add RSI/EMA/SMA signals in `backtesting/signals.py`.
2) Add `backtesting/report.py` ranked table output including B&H row.
3) Add `run_backtests.py` CLI for standalone runs.
4) Validate output schema and fail on NaN/invalid rows.
Do not add full indicator inventory yet.
```

---

## Milestone 3 — Full Indicator Set + Optimization

**Goal:** complete requirement indicator list and optimization while controlling combinatorial explosion.

---

### Sprint 3.1 — Complete Indicator Inventory (All Required)

**Goal:** add remaining required indicators with bounded parameter surfaces.

#### Deliverables

| File | Change |
|------|--------|
| `backtesting/signals.py` | Add Stochastic, MACD, Bollinger %B, CCI, UO, MFI, ADX, PSAR, Heikin Ashi |
| `backtesting/parameter_space.py` | Defines per-indicator parameter ranges |
| `scripts/verify_indicator_signals.py` | Quick per-indicator signal sanity checks |

#### Steps

1. Implement all remaining required indicators.
2. Define bounded search ranges with defaults and hard caps.
3. Ensure indicators needing volume (MFI) fail gracefully when unavailable.
4. Keep Heikin Ashi as non-optimized buy condition (`HA close > HA open`).

#### Error Correction Protocol

- Add per-indicator NaN/shape checks before engine call.
- If TA-Lib output diverges from expected shape, skip combo with logged reason.

#### Exit Criteria

- [ ] All required indicators executable on all 3 timeframes (where data valid).
- [ ] Parameter surfaces defined and bounded.
- [ ] Signal sanity script passes.

#### Copy/Paste Prompt (Sprint 3.1)

```markdown
Implement Sprint 3.1 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Add remaining required indicators to `backtesting/signals.py`.
2) Add bounded parameter spaces in `backtesting/parameter_space.py`.
3) Add `scripts/verify_indicator_signals.py` and run it.
4) Enforce graceful skips for invalid/insufficient data.
Do not implement global optimization executor yet.
```

---

### Sprint 3.2 — Optimization Executor (Params + Trailing Stops)

**Goal:** implement constrained grid-search and trailing stop sweep selection logic.

#### Deliverables

| File | Change |
|------|--------|
| `backtesting/optimizer.py` | Param-grid runner + trailing stop sweep |
| `backtesting/selection.py` | Best-result selection per indicator/timeframe |
| `scripts/verify_optimizer_bounds.py` | Ensures combo limits (50–100 max) |

#### Steps

1. For each indicator/timeframe:
   - Evaluate parameter combos (cap at config max, default 100).
   - For each best param candidate, sweep trailing stop 0%..20% in 1% increments.
2. Select winner by max net profit.
3. Preserve full #1 settings payload for final output.

#### Error Correction Protocol

- Guardrail: abort any run that exceeds combo cap.
- Persist progress checkpoints to allow resume after interruption.

#### Exit Criteria

- [ ] Optimization respects max combo caps.
- [ ] Trailing stop sweep applied consistently.
- [ ] Top result includes precise full parameter list.

#### Copy/Paste Prompt (Sprint 3.2)

```markdown
Implement Sprint 3.2 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Create `backtesting/optimizer.py` with combo cap enforcement.
2) Add 0%-20% trailing stop sweep in 1% increments.
3) Select best per indicator/TF by max net profit.
4) Persist precise #1 full settings payload.
5) Add optimizer bounds verification script.
Do not integrate into scanner pipeline yet.
```

---

## Milestone 4 — Scanner Integration + Parallelization + Reliability

**Goal:** run backtests only on final-stage Kraken-qualified coins, in parallel, with production-safe reporting.

---

### Sprint 4.1 — Pipeline Hook + Kraken Gate + Parallel Runner

**Goal:** integrate backtesting into `main.py` post-final-filter with strict exchange gate and worker pool.

#### Deliverables

| File | Change |
|------|--------|
| `main.py` | Add post-`final_results` backtest invocation behind feature flag |
| `backtesting/runner.py` | Parallel per-coin execution orchestration |
| `config/settings.py` | Worker/batch safety knobs |

#### Steps

1. Hook after final candidate list creation.
2. Only backtest coins listed on `BACKTEST_EXCHANGES` (default `kraken`).
3. Execute per coin in bounded process pool.
4. Write structured artifact (`backtest_results.json`) with summary + per-strategy rows.

#### Error Correction Protocol

- If worker crash occurs, isolate coin and continue run.
- If backtesting fails globally, scanner still completes and logs error.

#### Exit Criteria

- [ ] Hook runs only when `BACKTEST_ENABLED=true`.
- [ ] Kraken gating enforced and configurable.
- [ ] Parallel runner stable under partial failures.

#### Copy/Paste Prompt (Sprint 4.1)

```markdown
Implement Sprint 4.1 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Integrate backtest hook in `main.py` after final-stage filtering.
2) Enforce exchange gate using `BACKTEST_EXCHANGES` (default kraken).
3) Implement bounded parallel runner in `backtesting/runner.py`.
4) Ensure scanner remains resilient if backtest module fails.
Do not finalize presentation/telegram output yet.
```

---

### Sprint 4.2 — Final Output Contract + Reliability Hardening

**Goal:** finalize output contract exactly as required and harden for production reruns.

#### Deliverables

| File | Change |
|------|--------|
| `backtesting/report.py` | Final ranked table + top #1 settings block |
| `README.md` | Backtesting usage + config + troubleshooting section |
| `docs/backtesting-runbook.md` | Run/fix checklist and known failure modes |

#### Steps

1. Emit final ranked table sorted by net % descending with B&H row.
2. Emit precise #1 settings line with full parameter list.
3. Add runbook with retry/skip policy and verification commands.
4. Perform full integration run and capture known issues.

#### Error Correction Protocol

- Require non-empty final table and explicit skip reasons for excluded strategies.
- Validate numeric formatting and sorting before marking complete.

#### Exit Criteria

- [ ] Output contract exactly matches requested columns.
- [ ] Top #1 settings emitted with full parameter details.
- [ ] README and runbook updated for repeatable operation.

#### Copy/Paste Prompt (Sprint 4.2)

```markdown
Implement Sprint 4.2 from `backtesting-implementation-plan.md` only.
Scope lock:
1) Finalize ranked report output and top #1 settings output.
2) Update `README.md` with backtesting config/run instructions.
3) Add `docs/backtesting-runbook.md` with failure/recovery checklist.
4) Run full integration and record unresolved issues explicitly.
No extra features beyond documented requirements.
```

---

## Global Error-Prevention Rules (Apply in Every Sprint)

1. **Scope lock:** only implement current sprint deliverables.
2. **Run/fix loop:** code -> run smallest verification -> fix -> rerun.
3. **No silent fallback to wrong data model:** close-only daily data cannot substitute OHLCV.
4. **Determinism:** same input/config must produce same result ordering.
5. **Checkpoint artifacts:** save intermediate progress for resume after interruption.
6. **Failure transparency:** skip with reason; do not hide failed coins/strategies.

---

## Suggested Execution Order (Chronological)

1. Sprint 1.1
2. Sprint 1.2
3. Sprint 2.1
4. Sprint 2.2
5. Sprint 3.1
6. Sprint 3.2
7. Sprint 4.1
8. Sprint 4.2

This order is intentionally optimized to reduce rework and avoid introducing strategy-level complexity before environment and data correctness are proven.
