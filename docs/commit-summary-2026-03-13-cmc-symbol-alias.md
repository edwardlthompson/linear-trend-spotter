# Commit Summary — 2026-03-13 — CMC symbol alias fallback

## Scope

- Fix false negatives where exchange symbols differ from CoinMarketCap symbols (example: `CRYPGPT` vs `CGPT`).

## What changed

- Added CMC symbol resolution fallback in scanner flow:
  - direct symbol match,
  - configured alias match,
  - normalized-symbol fallback.
- Added `CMC_SYMBOL_ALIASES` config support with validation/normalization in `config/settings.py`.
- Added default alias mapping `{ "CRYPGPT": "CGPT" }`.
- Applied resolver in both:
  - Filter 1 qualification stage,
  - exit-reason attribution stage.
- Added CoinGecko ID fallback using resolved CMC symbol when exchange symbol mapping is missing.
- Updated `config.json.example` and README config table.

## Why this deviates from prior logic

- Previous logic required exact `symbol == CMC symbol`, which dropped valid candidates early and created misleading "perfect qualifications" expectations.
- New logic intentionally deviates to prefer deterministic alias resolution before rejection, improving correctness without broad fuzzy matching.

## Validation

- Static diagnostics: no errors in updated files.
- Smoke test confirmed:
  - `CRYPGPT` resolves to `CGPT` via configured alias.
  - direct symbols (e.g., `BTC`) still resolve directly.
