from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(255))
    date_joined = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    portfolios = db.relationship(
        "Portfolio", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    rate_limits = db.relationship(
        "SummaryLimit", backref="user", lazy=True, cascade="all, delete-orphan"
    )


class Portfolio(db.Model):
    __tablename__ = "portfolios"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "ticker_symbol", name="uq_user_ticker"),
    )


class SummaryLimit(db.Model):
    __tablename__ = "summary_limits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    count = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_user_date"),
    )
