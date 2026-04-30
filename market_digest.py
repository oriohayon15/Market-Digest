#!/usr/bin/env python3
"""
Market Digest
Fetches price data, news, and AI summaries for your watchlist — then texts them to you.

Build stages:
  Step 1 (done): Price data for one ticker
  Step 2 (done): News headlines
  Step 3 (current): Claude AI summaries with full article text
  Step 4: SMS delivery
"""

from datetime import datetime, timezone
import os
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
import requests
import yfinance as yf

load_dotenv()
_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ── Your watchlist ────────────────────────────────────────────────────────────
# Stocks use plain symbols (NVDA, AAPL). Crypto appends -USD (BTC-USD, ETH-USD).
TICKERS = ["NVDA"]


# ── Step 1: Price data ────────────────────────────────────────────────────────

def get_price_data(ticker: str) -> dict:
    """Return today's closing price and % change vs. previous close."""
    stock = yf.Ticker(ticker)

    # Pull the last 5 trading days so we always have a valid "previous close"
    # even after weekends or holidays.
    hist = stock.history(period="5d")

    if len(hist) < 2:
        raise ValueError(f"Not enough history for {ticker}")

    current_price = hist["Close"].iloc[-1]
    prev_close    = hist["Close"].iloc[-2]
    pct_change    = (current_price - prev_close) / prev_close * 100

    return {
        "ticker":     ticker,
        "price":      current_price,
        "pct_change": pct_change,
    }


def format_price_line(data: dict) -> str:
    arrow = "▲" if data["pct_change"] >= 0 else "▼"
    sign  = "+" if data["pct_change"] >= 0 else ""
    return f"{data['ticker']}: ${data['price']:.2f}  {arrow} {sign}{data['pct_change']:.2f}%"


# ── Step 2 + 3: News with full article text ───────────────────────────────────

def fetch_article_text(url: str, max_chars: int = 2000) -> str:
    """
    Download a news article and return its body text.
    Returns empty string if the page is paywalled or blocks us — Claude
    will fall back to the headline alone in that case.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MarketDigest/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strip nav/footer/script noise before grabbing paragraphs
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 40)  # skip short nav fragments
        return text[:max_chars]
    except Exception:
        return ""


def get_news(ticker: str, max_articles: int = 4) -> tuple[list[dict], bool]:
    """
    Return (articles, is_fresh) where:
      - articles is a list of {title, text} dicts
      - is_fresh=True if at least one article is from today,
        is_fresh=False if we fell back to recent articles

    Always returns something — falls back to the most recent articles
    available if nothing was published today.
    """
    stock = yf.Ticker(ticker)
    today = datetime.now(timezone.utc).date()

    today_articles  = []
    recent_articles = []

    for item in stock.news:
        # yfinance news item structure varies by version; fall back gracefully
        raw = item.get("content", item)  # newer versions nest data under "content"
        ts  = raw.get("pubDate") or raw.get("providerPublishTime")
        if isinstance(ts, str):
            from dateutil.parser import parse as parse_dt
            pub_date = parse_dt(ts).date()
        elif ts:
            pub_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        else:
            pub_date = None
        url = raw.get("canonicalUrl", {}).get("url", "") if isinstance(raw.get("canonicalUrl"), dict) else raw.get("link", "")
        text     = fetch_article_text(url) if url else ""

        title   = raw.get("title", "")
        article = {
            "title": title,
            "text":  text,
        }

        if pub_date == today:
            today_articles.append(article)
        else:
            recent_articles.append(article)

        # Stop once we have enough of whichever bucket is filling
        if len(today_articles) >= max_articles:
            break
        if not today_articles and len(recent_articles) >= max_articles:
            break

    if today_articles:
        return today_articles, True
    return recent_articles[:max_articles], False


# ── Step 3: Claude AI summary ─────────────────────────────────────────────────

def get_ai_summary(ticker: str, price_data: dict, articles: list[dict], is_fresh: bool) -> str:
    """Ask Gemini to write a 2-3 sentence explanation of the day's move."""
    direction = "up" if price_data["pct_change"] >= 0 else "down"

    article_blocks = []
    for a in articles:
        if a["text"]:
            article_blocks.append(f"Headline: {a['title']}\n{a['text']}")
        else:
            article_blocks.append(f"Headline: {a['title']}")
    articles_text = "\n\n---\n\n".join(article_blocks)

    if is_fresh:
        context_note = "Here is today's news coverage:"
        instruction  = (
            f"In 2-3 sentences, explain why {ticker} moved the way it did today "
            f"based on this coverage. Be direct and specific."
        )
    else:
        context_note = "There was no major news published today. Here is the most recent coverage:"
        instruction  = (
            f"In 2-3 sentences, note that there wasn't much news today for {ticker} "
            f"and briefly summarize the recent context that may be influencing the move."
        )

    prompt = f"""{ticker} moved {direction} {abs(price_data['pct_change']):.2f}% today, closing at ${price_data['price']:.2f}.

{context_note}

{articles_text}

{instruction} No filler phrases."""

    for attempt in range(4):
        try:
            response = _gemini.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return response.text
        except Exception as e:
            if attempt == 3:
                raise
            wait = 15 * (2 ** attempt)  # 15s, 30s, 60s
            print(f"  Gemini unavailable, retrying in {wait}s…")
            time.sleep(wait)


# ── Step 4: Push notification ─────────────────────────────────────────────────

def send_notification(body: str) -> None:
    requests.post(
        f"https://ntfy.sh/{os.getenv('NTFY_TOPIC')}",
        data=body.encode("utf-8"),
        headers={"Title": "Market Digest"},
        timeout=10,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("📈 Market Digest\n")
    lines = []
    for ticker in TICKERS:
        try:
            price_data           = get_price_data(ticker)
            articles, is_fresh   = get_news(ticker)
            summary              = get_ai_summary(ticker, price_data, articles, is_fresh)

            block = f"{format_price_line(price_data)}\n{summary}"
            print(block)
            print()
            lines.append(block)
        except Exception as e:
            print(f"{ticker}: error — {e}")

    if lines:
        send_notification("\n\n".join(lines))


if __name__ == "__main__":
    main()
