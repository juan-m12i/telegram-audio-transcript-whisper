import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler, CallbackQueryHandler
from adapters.notion_adapter import NotionAdapter
from bot.bot_actions import action_ping
from bot.bot_common import run_telegram_bot, reply_builder, allowed_user
from bot.bot_conditions import condition_ping, condition_catch_all
from notes_bot import action_notes

load_dotenv()  # Python module to load environment variables from a .env file

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(
    ',')]  # Pythonic way of creating a list, behaves like a loop

my_notion = NotionAdapter(os.getenv("NOTION_TOKEN"))


from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    query_data = query.data

    if query_data == "GPT3":
        await query.message.reply_text("Send me a message to get a GPT-3 response.")
    elif query_data == "GPT4":
        await query.message.reply_text("Send me a message to get a GPT-4 response.")
    elif query_data == "Summary":
        await query.message.reply_text("Send me a message to get a summary.")


async def draw_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        logging.info(f"Drawing buttons for verified user")

        keyboard = [
            [
                InlineKeyboardButton("GPT-3", callback_data="GPT3"),
                InlineKeyboardButton("GPT-4", callback_data="GPT4"),
            ],
            [
                InlineKeyboardButton("Summary", callback_data="Summary"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Choose an option:", reply_markup=reply_markup
        )



reply = reply_builder({
    condition_ping: action_ping,
    condition_catch_all: action_notes,
})


def run_dev_bot():
    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    start_handler = CommandHandler('start', draw_buttons)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    callback_handler = CallbackQueryHandler(button_callback)

    run_telegram_bot(os.getenv('TELEGRAM_BOT_TOKEN'), [start_handler, echo_handler, callback_handler])


if __name__ == '__main__':
    run_dev_bot()
