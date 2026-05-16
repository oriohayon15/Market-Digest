from datetime import date
from functools import wraps

import yfinance as yf
from flask import has_app_context

from app.bot import bot
from app.config import Config
from app.models import Portfolio, SummaryLimit, User, db
from app.services.ai import get_ai_summary
from app.services.market import format_price_line, get_news, get_price_data

_flask_app = None


def init_handlers(app):
    global _flask_app
    _flask_app = app


def _with_context(f):
    """Push a Flask app context if one isn't already active (needed for polling mode)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if has_app_context():
            return f(*args, **kwargs)
        with _flask_app.app_context():
            return f(*args, **kwargs)
    return wrapper


HELP_TEXT = (
    "📈 *Market Digest*\n"
    "Get a daily AI-powered summary of your stock portfolio, delivered every weekday at 4pm ET.\n\n"
    "*Commands*\n"
    "/add AAPL — add a ticker to your portfolio\n"
    "/remove AAPL — remove a ticker from your portfolio\n"
    "/portfolio — view all tickers you're tracking\n"
    "/summary — get an on-demand digest right now\n"
    "/help — show this message"
)


def _is_valid_ticker(symbol: str) -> bool:
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        return not hist.empty
    except Exception:
        return False


@bot.message_handler(commands=["start"])
@_with_context
def cmd_start(message):
    user = User.query.filter_by(telegram_id=message.from_user.id).first()
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        db.session.add(user)
        db.session.commit()
        bot.send_message(message.chat.id, "Welcome to Market Digest! You've been registered.\n\n" + HELP_TEXT, parse_mode="Markdown")
    else:
        bot.reply_to(message, "Welcome back! You're already registered.")


@bot.message_handler(commands=["help"])
@_with_context
def cmd_help(message):
    bot.send_message(message.chat.id, HELP_TEXT, parse_mode="Markdown")


@bot.message_handler(commands=["add"])
@_with_context
def cmd_add(message):
    user = User.query.filter_by(telegram_id=message.from_user.id).first()
    if not user:
        bot.reply_to(message, "You're not registered yet. Send /start first.")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Please provide a ticker. Example: /add AAPL")
        return

    ticker = parts[1].upper()

    existing = Portfolio.query.filter_by(user_id=user.id, ticker_symbol=ticker).first()
    if existing:
        bot.reply_to(message, f"{ticker} is already in your portfolio.")
        return

    current_count = Portfolio.query.filter_by(user_id=user.id).count()
    if not user.is_admin and current_count >= 10:
        bot.reply_to(message, "You've reached the 10 ticker limit. Remove one with /remove before adding another.")
        return

    if not _is_valid_ticker(ticker):
        bot.reply_to(message, f"'{ticker}' doesn't look like a valid ticker. Please double-check the symbol.")
        return

    db.session.add(Portfolio(user_id=user.id, ticker_symbol=ticker))
    db.session.commit()

    new_count = current_count + 1
    if not user.is_admin and new_count >= 5:
        remaining = 10 - new_count
        bot.reply_to(message, f"{ticker} added to your portfolio.\n\nReminder: you can track a maximum of 10 stocks. You have {remaining} remaining.")
    else:
        bot.reply_to(message, f"{ticker} added to your portfolio.")


@bot.message_handler(commands=["remove"])
@_with_context
def cmd_remove(message):
    user = User.query.filter_by(telegram_id=message.from_user.id).first()
    if not user:
        bot.reply_to(message, "You're not registered yet. Send /start first.")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Please provide a ticker. Example: /remove AAPL")
        return

    ticker = parts[1].upper()

    entry = Portfolio.query.filter_by(user_id=user.id, ticker_symbol=ticker).first()
    if not entry:
        bot.reply_to(message, f"{ticker} is not in your portfolio.")
        return

    db.session.delete(entry)
    db.session.commit()
    bot.reply_to(message, f"{ticker} removed from your portfolio.")


@bot.message_handler(commands=["portfolio"])
@_with_context
def cmd_portfolio(message):
    user = User.query.filter_by(telegram_id=message.from_user.id).first()
    if not user:
        bot.reply_to(message, "You're not registered yet. Send /start first.")
        return

    tickers = Portfolio.query.filter_by(user_id=user.id).all()
    if not tickers:
        bot.reply_to(message, "Your portfolio is empty. Use /add AAPL to start tracking tickers.")
        return

    symbols = "\n".join(f"• {t.ticker_symbol}" for t in tickers)
    bot.reply_to(message, f"Your portfolio:\n{symbols}")


@bot.message_handler(commands=["summary"])
@_with_context
def cmd_summary(message):
    user = User.query.filter_by(telegram_id=message.from_user.id).first()
    if not user:
        bot.reply_to(message, "You're not registered yet. Send /start first.")
        return

    tickers = Portfolio.query.filter_by(user_id=user.id).all()
    if not tickers:
        bot.reply_to(message, "Your portfolio is empty. Use /add AAPL to start tracking tickers.")
        return

    today = date.today()
    limit_row = SummaryLimit.query.filter_by(user_id=user.id, date=today).first()
    if not user.is_admin and limit_row and limit_row.count >= Config.SUMMARY_DAILY_LIMIT:
        bot.reply_to(message, f"You've reached your {Config.SUMMARY_DAILY_LIMIT} on-demand summary limit for today. Your next digest arrives at 4pm EST.")
        return

    bot.reply_to(message, "Generating your portfolio digest... this may take a moment.")

    blocks = []
    for entry in tickers:
        ticker = entry.ticker_symbol
        try:
            price_data = get_price_data(ticker)
            articles, is_fresh = get_news(ticker)
            summary = get_ai_summary(ticker, price_data, articles, is_fresh)
            blocks.append(f"{format_price_line(price_data)}\n{summary}")
        except Exception:
            blocks.append(f"{ticker}: data unavailable at this time.")

    if limit_row:
        limit_row.count += 1
    else:
        db.session.add(SummaryLimit(user_id=user.id, date=today, count=1))
    db.session.commit()

    if user.is_admin:
        footer = ""
    else:
        remaining = Config.SUMMARY_DAILY_LIMIT - (limit_row.count if limit_row else 1)
        footer = f"\n\n({remaining} on-demand {'summary' if remaining == 1 else 'summaries'} left today)"
    bot.reply_to(message, "📈 Market Digest\n\n" + "\n\n".join(blocks) + footer)
