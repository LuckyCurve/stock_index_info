# Stock Index Info Telegram Bot

A Telegram Bot to query which US stock indices (S&P 500, NASDAQ 100) a stock belongs to.

## Setup

### 1. Create a Telegram Bot

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 2. Get Your Telegram User ID

1. Talk to [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy your user ID

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run the Bot

```bash
TELEGRAM_BOT_TOKEN=your_bot_token ALLOWED_USER_IDS=your_user_id uv run stock-index-bot
```

For multiple allowed users, separate IDs with commas:
```bash
ALLOWED_USER_IDS=123456789,987654321
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and command list |
| `/help` | Show help message |
| `/query <TICKER>` | Query which indices a stock belongs to |
| `/constituents <INDEX>` | List current constituents (sp500 or nasdaq100) |
| `/sync` | Sync data from Wikipedia manually |
| `/status` | Show bot status and next sync time |

## Auto-Sync

The bot automatically syncs data from Wikipedia daily at 2:00 AM (configurable via `SYNC_HOUR` and `SYNC_MINUTE` env vars).

You can also send a ticker symbol directly (e.g., `AAPL`) without any command.

## Example Output

```
AAPL

P/E (7Y Avg): 28.5 | Avg Income: $85.2B

Index Membership:
Index        Added        Removed      Years
--------------------------------------------
S&P 500      1982-11-30   -            43.0
NASDAQ 100   1985-01-31   -            40.0

SEC Filings:
Quarterly (10-Q):
  2024-08-02: https://www.sec.gov/Archives/edgar/data/...
  2024-05-03: https://www.sec.gov/Archives/edgar/data/...
Annual (10-K):
  2023-11-03: https://www.sec.gov/Archives/edgar/data/...

Reuters Valuation: AAPL.O | AAPL.N | AAPL
```

The `/query` command displays:
- **7-Year Average P/E Ratio** - Calculated using historical net income from Alpha Vantage and current market cap from Yahoo Finance. Shows both P/E ratio and 7-year average net income (requires `ALPHA_VANTAGE_API_KEY`). Non-USD currencies are automatically converted.
- **Index Membership** - S&P 500 and NASDAQ 100 membership history
- **SEC Filings** - Up to 4 quarterly 10-Q reports and the latest annual 10-K report from SEC EDGAR
- **Reuters Valuation Links** - Quick links to Reuters valuation page (tries NASDAQ .O, NYSE .N, and no-suffix variants)

## CSV Data

The CSV files in `data/` are updated periodically and can be used directly:

| File | Description |
|------|-------------|
| `data/sp500.csv` | S&P 500 constituents |
| `data/nasdaq100.csv` | NASDAQ 100 constituents |

CSV fields: `ticker`, `company_name`, `added_date`, `removed_date`

To manually update the CSV files:
```bash
uv run python scripts/export_csv.py
```

## Development

```bash
# Run tests
uv run pytest -v

# Type check
uv run mypy src/

# Lint
uv run ruff check src/ tests/
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
| `ALLOWED_USER_IDS` | Yes | Comma-separated Telegram user IDs |
| `SYNC_HOUR` | No | Hour for daily sync (0-23, default: 2) |
| `SYNC_MINUTE` | No | Minute for daily sync (0-59, default: 0) |
| `ALPHA_VANTAGE_API_KEY` | No | Alpha Vantage API key for 7-year average P/E feature |

## Running in Background

### Using nohup
```bash
nohup uv run stock-index-bot > bot.log 2>&1 &
```

### Using screen
```bash
screen -S stock-bot
uv run stock-index-bot
# Press Ctrl+A, then D to detach
```

### Using systemd (recommended for production)

Create `/etc/systemd/system/stock-index-bot.service`:
```ini
[Unit]
Description=Stock Index Info Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/stock_index_info
Environment=TELEGRAM_BOT_TOKEN=your_token
Environment=ALLOWED_USER_IDS=your_user_id
ExecStart=/path/to/.local/bin/uv run stock-index-bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-index-bot
sudo systemctl start stock-index-bot
```
