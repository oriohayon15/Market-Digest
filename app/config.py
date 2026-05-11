import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    PORT = int(os.environ.get("PORT", 5000))
    SUMMARY_DAILY_LIMIT = 3

    @classmethod
    def get_db_url(cls) -> str:
        url = cls.DATABASE_URL
        # Railway gives mysql://, SQLAlchemy needs mysql+pymysql://
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        return url
