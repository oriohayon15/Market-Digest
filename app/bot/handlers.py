from functools import wraps

import yfinance as yf
from flask import has_app_context

from app.bot import bot
from app.models import Portfolio, User, db

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
        bot.reply_to(message, "Welcome to Market Digest! You've been registered.")
    else:
        bot.reply_to(message, "Welcome back! You're already registered.")


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

    if not _is_valid_ticker(ticker):
        bot.reply_to(message, f"'{ticker}' doesn't look like a valid ticker. Please double-check the symbol.")
        return

    db.session.add(Portfolio(user_id=user.id, ticker_symbol=ticker))
    db.session.commit()
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
