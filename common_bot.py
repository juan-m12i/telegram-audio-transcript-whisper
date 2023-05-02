import os
import logging
from typing import List, Callable, Coroutine
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram import Update


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


def bot_start(welcome_message: str) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine]:
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if allowed_user(update):
            await update.message.reply_text(welcome_message)

    return start_command


def add_handlers(bot, *handlers):
    for handler in handlers:
        bot.add_handler(handler)


