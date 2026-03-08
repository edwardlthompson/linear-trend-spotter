# Linear Trend Spotter

Automated full-exchange scanner for identifying coins with sustained trend quality (not one-candle pumps), then posting entry/exit alerts to Telegram.

[![Telegram Group](https://img.shields.io/badge/Telegram-Join%20Group-blue?logo=telegram)](https://t.me/+pmZewVhuEFJjYTIx)

---

## What It Does

Linear Trend Spotter scans all symbols listed across target exchanges (default: Coinbase, Kraken, MEXC), then applies a strict multi-step qualification pipeline:

1. CoinMarketCap snapshot pull (up to 5000 coins)
2. Exchange listing universe build (all symbols in `exchange_listings`)
3. Gain/volume filter
4. CoinGecko ID mapping
5. Exchange-volume enrichment (CoinGecko tickers)
6. 30-day uniformity scoring from market chart history
7. Entry/exit detection vs active list
8. Telegram notifications (with chart image when available)
9. History persistence + metrics/log summary

---

## Current Qualification Rules

### Filter 1: Volume + gains

- 24h CMC volume must be `>= MIN_VOLUME_M` (default `1,000,000`)
- 7d gain must be `> 7%`
- 30d gain must be `> 30%`
- 30d gain must be strictly higher than 7d gain (`30d > 7d`)
- Stablecoins are excluded

### Filter 2: Uniformity

- Uses 30-day price history (CoinGecko market chart)
- Computes a uniformity score from 0–100
- Must pass `UNIFORMITY_MIN_SCORE` (default `55`)
- Must also have positive 30d return

---

## Notification Behavior

### Entry notifications

- Sent once when a coin newly enters qualified state
- Includes:
  - Coin name/symbol with CMC link
  - 7d and 30d gains
  - Uniformity score
  - **Total 24h volume (CMC)**
  - Exchange-level volumes (Coinbase/Kraken/MEXC)
- Sends chart image when Chart-IMG is available; otherwise text-only fallback

### Exit notifications

- Sent once when a previously active coin leaves qualification
- Includes **precise exit reason** (first failed stage), for example:
  - 24h volume below threshold
  - 7d/30d threshold violation
  - `30d <= 7d`
  - Missing CMC/CoinGecko data
  - Uniformity score below threshold

---

## Caching + Rate Limit Strategy

- CoinGecko ticker requests use adaptive retry/backoff + jitter and `Retry-After` handling
- Non-critical ticker fetches fail fast after capped retries to prevent full-run stalls
- Exchange-volume cache TTL: 24h (`exchange_volume_cache`)
- Price/uniformity cache TTL: 6h (`price_cache`)

---

## Configuration

### 1) Environment variables (`.env`)

```env
CMC_API_KEY=your_cmc_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
CHART_IMG_API_KEY=your_chart_img_api_key_optional
```

### 2) App config (`config.json`)

Start from `config.json.example`:

```powershell
Copy-Item config.json.example config.json
```

Available parameters (defaults from `config/settings.py`):

| Key | Default | Purpose |
|---|---:|---|
| `MIN_VOLUME_M` | `1000000` | Minimum 24h CMC volume gate |
| `TARGET_EXCHANGES` | `['coinbase','kraken','mexc']` | Exchanges scanned/listed |
| `UNIFORMITY_MIN_SCORE` | `55` | Uniformity filter cutoff |
| `UNIFORMITY_PERIOD` | `30` | Days used for score window |
| `TOP_COINS_LIMIT` | `2500` | General list limit control |
| `ENTRY_NOTIFICATIONS` | `true` | Enable entry alerts |
| `EXIT_NOTIFICATIONS` | `true` | Enable exit alerts |
| `RETRY_MAX_ATTEMPTS` | `3` | Generic retry attempts |
| `RETRY_DELAY` | `2` | Base retry delay |
| `RETRY_BACKOFF` | `2` | Retry backoff factor |
| `COINGECKO_CALLS_PER_MINUTE` | `30` | CoinGecko pacing target |
| `CMC_CALLS_PER_MINUTE` | `333` | CMC pacing target |
| `CACHE_GECKO_ID_DAYS` | `30` | Mapping cache TTL |
| `CACHE_EXCHANGE_HOURS` | `24` | Exchange-volume cache TTL |
| `CACHE_PRICE_HOURS` | `6` | Price/uniformity cache TTL |
| `CIRCUIT_FAILURE_THRESHOLD` | `5` | Circuit breaker fail threshold |
| `CIRCUIT_RECOVERY_TIMEOUT` | `60` | Circuit recovery timeout (sec) |
| `USE_14D_FILTER` | `false` | Reserved feature flag |

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Initialize/refresh support data:

```powershell
python update_mappings.py
python update_exchanges.py
```

Run a single scan:

```powershell
python main.py
```

---

## Operations

Useful operational scripts in this repo:

- `scheduler.py` — scheduled scanner execution
- `manage_bot.py` — bot process management helpers
- `bot_watchdog.py` — process health monitoring/restarts
- `update_exchanges.py` — exchange listing refresh
- `update_mappings.py` — mapping refresh

Suggested cadence:

- Scanner: hourly
- Exchange listing refresh: weekly
- Mapping refresh: monthly
- Watchdog: every 5 minutes

---

## Logs and Outputs

- `trend_scanner.log` — full pipeline runtime log and summaries
- `bot_output.log` — Telegram/bot-side output
- `metrics.json` — persisted metrics snapshot

---

## Notes

- If Chart-IMG key is missing, alerts still send as text-only.
- If public CoinGecko limit pressure is high, scanner degrades gracefully using cache + fail-fast behavior on non-critical ticker fetches.
