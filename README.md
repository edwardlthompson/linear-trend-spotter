# Linear Trend Spotter

**Automated full-exchange scanner that identifies coins with strong, sustainable growth patterns.**

Linear Trend Spotter continuously scans every coin listed on Coinbase, Kraken, and MEXC, applies a multi-stage filtering pipeline, and delivers real-time alerts — complete with professional chart images — directly to a Telegram group. It runs 24/7 so you don't have to.

[![Telegram Group](https://img.shields.io/badge/Telegram-Join%20Group-blue?logo=telegram)](https://t.me/+pmZewVhuEFJjYTIx)

---

## Problem

Most traders face the same challenge: sifting through thousands of coins across multiple exchanges to find genuine, sustained momentum — not just short-lived pumps. Manual screening is time-consuming and error-prone, and most free tools lack the nuance to distinguish smooth uptrends from sudden spikes.

Linear Trend Spotter automates the entire discovery process with a data-driven approach.

## How It Works

The system applies a three-stage filtering pipeline to every listed coin on the target exchanges.

### Stage 1 — Fundamental Filters

- **Volume gate:** Coins must exceed a minimum 24-hour trading volume (default: $1 M) to ensure adequate liquidity.
- **Multi-timeframe gain thresholds:** Average daily growth must be greater than 1% over both 7-day (cumulative > 7%) and 30-day (cumulative > 30%) windows. This eliminates one-off spikes and dead-cat bounces.

### Stage 2 — Uniformity Analysis

This is the core differentiator. The system analyzes 30 days of price history and calculates a **Uniformity Score** (0–100) that measures how evenly gains are distributed across the period.

| Score Range | Interpretation |
|:-----------:|----------------|
| **45+**     | Smooth, reliable uptrend — gains are spread consistently across the window. |
| **< 45**    | Uneven distribution — e.g., "hockey stick" charts where most gains cluster at the end. Automatically excluded. |

### Stage 3 — Chart Generation

When a coin passes both filters, the system generates a TradingView-style chart image showing the 30-day price action and attaches it directly to the Telegram notification.

## Alert Behavior

Notifications follow a clean **enter/exit** model:

- **Entry alert** — Sent once when a coin first qualifies, including the chart image, Uniformity Score, 7-day and 30-day gain percentages, and exchange volume data.
- **Exit alert** — Sent once when a coin falls below the qualifying thresholds.

No repeated alerts, no spam.

## Infrastructure

| Component       | Detail |
|-----------------|--------|
| **Hosting**     | [PythonAnywhere](https://www.pythonanywhere.com/) cloud (~$10/month) |
| **Runtime**     | Python — runs continuously as a scheduled/always-on task |
| **Exchanges**   | Coinbase, Kraken, MEXC (full listing coverage) |
| **Delivery**    | Telegram Bot API |

## Setup Instructions

### Prerequisites

- Python 3.10+
- PythonAnywhere account (or any Linux server with cron)

### Configuration

1. **Environment Variables** — Copy `.env.example` to `.env` and configure:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

2. **Application Config** — Copy `config_json.example` to `config.json` and adjust settings as needed:
   - Minimum volume threshold
   - Gain filter percentages
   - Target exchanges
   - Rate limits

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Databases**:
   ```bash
   python update_mappings.py
   python update_exchanges.py
   ```

5. **Schedule Tasks** — Configure cron jobs (PythonAnywhere or standard cron):
   - `55 * * * *` — `scheduler.py` (hourly scan)
   - `0 0 * * 0` — `update_exchanges.py` (weekly)
   - `0 0 1 * *` — `update_mappings.py` (monthly)
   - `*/5 * * * *` — `bot_watchdog.py` (bot health check)

6. **Start Bot**:
   ```bash
   python manage_bot.py start
   ```

### Logs

- `trend_scanner.log` — Scanner pipeline output
- `bot_output.log` — Telegram bot activity

## Acknowledgments

This project was built with assistance from the [DeepSeek](https://www.deepseek.com/) coding agent.

## Join

👉 **[Join the Telegram group](https://t.me/+pmZewVhuEFJjYTIx)** to see the scanner in action and receive alerts in real time.
