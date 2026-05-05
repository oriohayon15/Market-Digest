import telebot

from app.config import Config

bot = telebot.TeleBot(Config.TELEGRAM_BOT_TOKEN)
