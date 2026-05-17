# Market Digest

A Telegram bot that delivers AI-powered stock summaries straight to your phone every day when the market closes. Track the stocks you care about, see price movements with context, and never have to open a news app just to understand why a stock moved.

---

## What it does

Each weekday at **4pm ET**, every registered user receives a personalized digest for the tickers in their portfolio. Each entry shows:

- The **closing price** and **percentage change** (▲ or ▼) vs. the previous close
- A **2–3 sentence AI summary** explaining why the stock moved, based on that day's news

The AI pulls the latest articles from Yahoo Finance, reads the full article text, and feeds it to OpenAI's GPT-4o-mini to generate a concise, plain-English explanation — so you get price and context in the same notification without switching apps.

Users can also call `/summary` at any time to get an on-demand digest without waiting for market close.

---

## Commands

| Command | Description |
|---|---|
| `/start` | Register your account |
| `/add AAPL` | Add a ticker to your portfolio |
| `/remove AAPL` | Remove a ticker from your portfolio |
| `/portfolio` | View all tickers you're currently tracking |
| `/summary` | Get a digest right now, on demand |
| `/help` | Show all commands |

Stocks use standard symbols (`NVDA`, `AAPL`). Crypto appends `-USD` (`BTC-USD`, `ETH-USD`).

---

## Limits

| Limit | Value |
|---|---|
| Max tickers per user | 10 |
| On-demand `/summary` calls per day | 3 |
| Automatic daily digest | Every weekday at 4pm ET |

The bot skips weekends and market holidays automatically using the NYSE trading calendar. Admin accounts bypass rate limits.

---

## Tech stack

| Layer | Technology |
|---|---|
| Bot framework | [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) |
| Web server | Flask |
| Database | MySQL (via SQLAlchemy) |
| Price data | yfinance |
| News scraping | yfinance + BeautifulSoup |
| AI summaries | OpenAI GPT-4o-mini |
| Scheduler | APScheduler + pandas_market_calendars |
| Deployment | Railway |

---

## How it works

1. **Price data** — yfinance pulls the last 5 trading days of history for each ticker, giving an accurate % change even after weekends and holidays.

2. **News** — yfinance returns a list of recent articles for each ticker. The bot fetches the full article body (stripping nav/footer noise with BeautifulSoup) and prefers articles published today. If there's no fresh news, it falls back to the most recent coverage and notes that in the summary.

3. **AI summary** — The article text and price data are sent to GPT-4o-mini with a prompt asking for a 2–3 sentence explanation of the day's move. The model is told to be direct and skip filler phrases.

4. **Delivery** — The scheduler fires daily at 4pm ET on market days. Each unique ticker is fetched once and cached, then each user receives a personalized message built from their own portfolio. On-demand `/summary` calls follow the same pipeline with a per-user daily rate limit.

---