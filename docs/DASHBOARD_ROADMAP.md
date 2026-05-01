# Dashboard enhancement roadmap (executed in-repo)

## Goals

1. **More columns** — 7d gain, per-exchange volume (from `exchange_volumes`), listed exchanges, volume acceleration (% + window days).
2. **Exchange filter** — Show only coins with `listed_on` containing the selected target exchange (union of exchanges present in snapshot).
3. **Tier-A notifications** — Browser “update alerts” compare **filtered** symbol sets between polls; notify when the filtered view changes (new/removed vs last poll under current filters).
4. **Backtest UX** — Keep row expand for quick peek; add **click name** → modal dialog with formatted backtest JSON + buy/hold (same data as expanded detail, larger readable layout).

## Data pipeline

| Feature | Source |
|--------|--------|
| 7d / 30d | Already in snapshot `gains` |
| Per-exchange volume | `exchange_volumes` (full `field_set` only) |
| Listed exchanges | `listed_on` on each coin — **added to snapshot writer** |
| Volume acceleration | `volume_acceleration_pct`, `volume_acceleration_window_days` — **added to snapshot writer** |

Worker must use **`PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET`: `full`** (or default full) for exchange volumes + backtest blocks.

## Files touched

- `utils/scan_artifacts.py` — emit `listed_on`, acceleration fields in `build_public_qualified_snapshot`.
- `tests/test_public_snapshot.py` — coverage for new fields.
- `docs/dashboard/index.html` — table headers, exchange `<select>`, `<dialog>` for backtest.
- `docs/dashboard/app.js` — filters, render, sort keys, filtered notifications, modal.
- `docs/dashboard/styles.css` — modal + wide table helpers.

## Non-goals (later)

- Separate route `/coin.html?symbol=` (could replace modal).
- Server-side backtest API (snapshot already carries strategy rows when enabled).
