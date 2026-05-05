from functools import wraps

from flask import has_app_context

from app.bot import bot
from app.models import User, db

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
