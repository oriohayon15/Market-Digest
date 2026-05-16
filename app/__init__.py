from flask import Flask
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
    init_handlers(app)

    from app.scheduler import init_scheduler
    init_scheduler(app)

    return app
