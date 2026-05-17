import telebot
from flask import Flask, request
from app.config import Config
from app.models import db


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = Config.get_db_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        print("Database tables ready.")

    from app.bot.handlers import init_handlers
    from app.bot import handlers as _handlers  # noqa — registers all handlers with the bot
    from app.bot import bot
    init_handlers(app)

    from app.scheduler import init_scheduler
    init_scheduler(app)

    if Config.WEBHOOK_URL:
        webhook_path = f"/{Config.TELEGRAM_BOT_TOKEN}"

        @app.route(webhook_path, methods=["POST"])
        def webhook():
            update = telebot.types.Update.de_json(request.get_data().decode("UTF-8"))
            bot.process_new_updates([update])
            return "ok", 200

        bot.remove_webhook()
        bot.set_webhook(url=Config.WEBHOOK_URL + webhook_path)
        print(f"Webhook registered: {Config.WEBHOOK_URL + webhook_path}")

    return app
