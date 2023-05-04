import os
import logging
from typing import List, Callable, Coroutine, TypeVar, Any, Dict
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, ContextTypes, Application
from telegram import Update

from bot.bot_lookup import bots_lookup
from bot.bot_types import ReplyAction, Condition

load_dotenv()  # Python module to load environment variables from a .env file

# Configure logging (native python library)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]


def allowed_user(update: Update) -> bool:
    return update.effective_chat.id in allowed_chat_ids


def bot_start(welcome_message: str) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine]:
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if allowed_user(update):
            await update.message.reply_text(welcome_message)

    return start_command


def reply_builder(actions: Dict[Condition, ReplyAction]) -> ReplyAction:
    async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if allowed_user(update):
            logging.info(f"Replying message from verified user")
            received_message_text = update.message.text

            for condition, action in actions.items():
                if condition(received_message_text):
                    await action(update, context)
                    break
            else:
                await update.message.reply_text("I don't know how to answer to that")

    return reply


def build_bot(token: str) -> Application:
    return ApplicationBuilder().token(token).build()


Handler = TypeVar("Handler", bound=Any)


def run_telegram_bot(token: str, handlers: List[Handler]):
    # This comes directly from the telegram bot library
    bot = build_bot(token)

    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    for handler in handlers:
        bot.add_handler(handler)

    # The app will be running constantly checking for new events

    bot_token_fingerprint = f"{token[:4]}..{token[-4:]}"
    logging.info(f"Running telegram bot {bot_token_fingerprint} - {bots_lookup.get(bot_token_fingerprint)}")
    bot.run_polling()
