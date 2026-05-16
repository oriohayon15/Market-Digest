from datetime import date

import pandas_market_calendars as mcal
from apscheduler.schedulers.background import BackgroundScheduler

from app.bot import bot
from app.models import Portfolio, User
from app.services.ai import get_ai_summary
from app.services.market import format_price_line, get_news, get_price_data


def _is_market_open_today() -> bool:
    nyse = mcal.get_calendar("NYSE")
    today = date.today()
    schedule = nyse.schedule(start_date=today, end_date=today)
    return not schedule.empty


def send_daily_digest(app):
    if not _is_market_open_today():
        print("[scheduler] Market closed today — skipping digest.")
        return

    with app.app_context():
        users = User.query.all()

        # Map each user to their tickers, skip users with empty portfolios.
        user_tickers: dict[int, list[str]] = {}
        for user in users:
            tickers = [e.ticker_symbol for e in Portfolio.query.filter_by(user_id=user.id).all()]
            if tickers:
                user_tickers[user.id] = tickers

        if not user_tickers:
            return

        # Fetch each unique ticker once.
        unique_tickers = {t for tickers in user_tickers.values() for t in tickers}
        cache: dict[str, str] = {}
        for ticker in unique_tickers:
            try:
                price_data = get_price_data(ticker)
                articles, is_fresh = get_news(ticker)
                summary = get_ai_summary(ticker, price_data, articles, is_fresh)
                cache[ticker] = f"{format_price_line(price_data)}\n{summary}"
            except Exception as e:
                print(f"[scheduler] {ticker} error: {e}")
                cache[ticker] = f"{ticker}: data unavailable at this time."

        # Send each user their personalised digest from the cache.
        for user in users:
            if user.id not in user_tickers:
                continue
            blocks = [cache[t] for t in user_tickers[user.id]]
            try:
                bot.send_message(
                    user.telegram_id,
                    "📈 Daily Market Digest\n\n" + "\n\n".join(blocks),
                )
            except Exception as e:
                print(f"[scheduler] Failed to send digest to {user.telegram_id}: {e}")


def init_scheduler(app):
    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(
        send_daily_digest,
        "cron",
        day_of_week="mon-sun",
        hour=16,
        minute=0,
        args=[app],
    )
    scheduler.start()
    return scheduler
