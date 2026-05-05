from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    if not Config.WEBHOOK_URL:
        from app.bot import bot
        print("No webhook URL set — running in polling mode.")
        bot.infinity_polling()
    else:
        app.run(host="0.0.0.0", port=Config.PORT, debug=False)
