import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler

load_dotenv()  # Python module to load environment variables from a .env file

# Configure logging (native python library)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]

def allowed_user(update: Update) -> bool:
    return update.effective_chat.id in allowed_chat_ids

def build_bot(token: str) -> ApplicationBuilder:
    return ApplicationBuilder().token(token).build()

def add_handlers(bot, *handlers):
    for handler in handlers:
        bot.add_handler(handler)
