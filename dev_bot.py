import os
import logging
from typing import List, Dict, Optional

import asyncio
import requests
from dotenv import load_dotenv
from telegram import Update, Bot, CallbackQuery
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler, CallbackQueryHandler
from adapters.notion_adapter import NotionAdapter
from bot.bot_actions import action_ping, action_reply_factory, action_unknown
from bot.bot_common import run_telegram_bot, reply_builder, allowed_user, send_startup_message
from bot.bot_conditions import condition_ping, condition_catch_all, condition_blue
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()  # Python module to load environment variables from a .env file

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(
    ',')]  # Pythonic way of creating a list, behaves like a loop

my_notion = NotionAdapter(os.getenv("NOTION_TOKEN"))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: Optional[CallbackQuery] = update.callback_query
    query_data = query.data

    if query_data == "GPT3":
        await query.message.reply_text("Send me a message to get a GPT-3 response.")
    elif query_data == "GPT4":
        await query.message.reply_text("Send me a message to get a GPT-4 response.")
    elif query_data == "Summary":
        await query.message.reply_text("Send me a message to get a summary.")
    elif query_data == "Blue":
        blue_quotes: Dict[str, float] = requests.get("https://api.bluelytics.com.ar/v2/latest").json().get("blue")
        await query.message.reply_text(f"Dolar Blue: {int(blue_quotes.get('value_buy'))} | {int(blue_quotes.get('value_sell'))}")


async def action_blue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    blue_quotes: Dict[str, float] = requests.get("https://api.bluelytics.com.ar/v2/latest").json().get("blue")
    await update.message.reply_text(
        f"Dolar Blue: {int(blue_quotes.get('value_buy'))} | {int(blue_quotes.get('value_sell'))}")


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
                InlineKeyboardButton("Blue", callback_data="Blue"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Choose an option:", reply_markup=reply_markup
        )
        blue_quotes: Dict[str, float] = requests.get("https://api.bluelytics.com.ar/v2/latest").json().get("blue")
        await update.message.reply_text(f"Dolar Blue: {int(blue_quotes.get('value_buy'))} | {int(blue_quotes.get('value_sell'))}")


reply = reply_builder({
    condition_ping: action_ping,
    condition_blue: action_blue,
    condition_catch_all: action_unknown,
})


def run_dev_bot():
    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot = Bot(token)

    start_handler = CommandHandler('start', draw_buttons)
    ver_handler = CommandHandler('ver', action_reply_factory(f"Dev Bot running on {os.getenv('THIS_MACHINE')}"))
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    callback_handler = CallbackQueryHandler(button_callback)

    loop = asyncio.get_event_loop()
    blue_quotes: Dict[str, float] = requests.get("https://api.bluelytics.com.ar/v2/latest").json().get("blue")
    loop.run_until_complete(send_startup_message(os.getenv('TELEGRAM_BOT_TOKEN'), allowed_chat_ids[0],
                                                 f"Dolar Blue: {int(blue_quotes.get('value_buy'))} | {int(blue_quotes.get('value_sell'))}"))

    logging.info("Starting DEV bot")
    run_telegram_bot(token, [start_handler, ver_handler, echo_handler, callback_handler])


if __name__ == '__main__':
    run_dev_bot()
