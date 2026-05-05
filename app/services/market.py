from datetime import datetime, timezone

import requests
import yfinance as yf
from bs4 import BeautifulSoup


def get_price_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d")
    if len(hist) < 2:
        raise ValueError(f"Not enough history for {ticker}")
    current_price = hist["Close"].iloc[-1]
    prev_close = hist["Close"].iloc[-2]
    pct_change = (current_price - prev_close) / prev_close * 100
    return {"ticker": ticker, "price": current_price, "pct_change": pct_change}


def format_price_line(data: dict) -> str:
    arrow = "▲" if data["pct_change"] >= 0 else "▼"
    sign = "+" if data["pct_change"] >= 0 else ""
    return f"{data['ticker']}: ${data['price']:.2f}  {arrow} {sign}{data['pct_change']:.2f}%"


def validate_ticker(ticker: str) -> bool:
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        return not hist.empty
    except Exception:
        return False


def fetch_article_text(url: str, max_chars: int = 2000) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MarketDigest/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 40)
        return text[:max_chars]
    except Exception:
        return ""


def get_news(ticker: str, max_articles: int = 4) -> tuple[list[dict], bool]:
    """Return (articles, is_fresh). Falls back to recent articles if no news today."""
    stock = yf.Ticker(ticker)
    today = datetime.now(timezone.utc).date()

    today_articles: list[dict] = []
    recent_articles: list[dict] = []

    for item in stock.news:
        raw = item.get("content", item)
        ts = raw.get("pubDate") or raw.get("providerPublishTime")
        if isinstance(ts, str):
            from dateutil.parser import parse as parse_dt
            pub_date = parse_dt(ts).date()
        elif ts:
            pub_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        else:
            pub_date = None

        url = (
            raw.get("canonicalUrl", {}).get("url", "")
            if isinstance(raw.get("canonicalUrl"), dict)
            else raw.get("link", "")
        )
        text = fetch_article_text(url) if url else ""
        article = {"title": raw.get("title", ""), "text": text}

        if pub_date == today:
            today_articles.append(article)
        else:
            recent_articles.append(article)

        if len(today_articles) >= max_articles:
            break
        if not today_articles and len(recent_articles) >= max_articles:
            break

    if today_articles:
        return today_articles, True
    return recent_articles[:max_articles], False
