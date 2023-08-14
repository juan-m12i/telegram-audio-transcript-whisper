import os
import logging
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler, CallbackQueryHandler
from adapters.notion_adapter import NotionAdapter
from bot.bot_actions import action_ping, action_reply_factory
from bot.bot_common import reply_builder, allowed_user, TelegramBot
from bot.bot_conditions import condition_ping, condition_catch_all
from notes_bot import action_notes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()  # Python module to load environment variables from a .env file

# Pythonic way of creating a list, behaves like a loop
allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]

my_notion = NotionAdapter(os.getenv("NOTION_TOKEN"))


def get_mep_quote() -> Optional[float]:
    response = requests.get("http://escuderokevin.com.ar:7070/api/dolarbolsa")
    mep_quote = response.json().get("venta")
    return mep_quote


async def send_mep_message(bot: TelegramBot, chat_ids: List[int]):
    mep_quote = get_mep_quote()
    for chat_id in chat_ids:
        await bot.send_message(chat_id, f"Dolar MEP: {mep_quote}")



def get_blue_quote():
    response = requests.get("https://api.bluelytics.com.ar/v2/latest")
    blue_quotes = response.json().get("blue")
    return blue_quotes


async def send_blue_message(bot: TelegramBot, chat_ids: List[int]):
    blue_quotes = get_blue_quote()
    for chat_id in chat_ids:
        await bot.send_message(chat_id, f"Dolar Blue: {int(blue_quotes.get('value_buy'))} | {int(blue_quotes.get('value_sell'))}")


def get_fx_quote(base: str, target: str) -> float:
    response = requests.get(f"https://anyapi.io/api/v1/exchange/rates?base={base}&apiKey={os.getenv('ANY_API_FX_KEY')}")
    rate = response.json().get("rates").get(target)
    return rate


async def send_fx_quote(bot: TelegramBot, chat_ids: List[int], base, target):
    fx_quote = get_fx_quote(base, target)
    for chat_id in chat_ids:
        await bot.send_message(chat_id, f"{base}/{target}: {round(fx_quote, 3)}")


async def send_gbp_usd_quote(bot: TelegramBot, chat_ids: List[int]):
    gbp_usd_quote = get_fx_quote("GBP", "USD")
    for chat_id in chat_ids:
        await bot.send_message(chat_id, f"GBP/USD: {round(gbp_usd_quote, 3)}")


async def send_eur_usd_quote(bot: TelegramBot, chat_ids: List[int]):
    eur_usd_quote = get_fx_quote("EUR", "USD")
    for chat_id in chat_ids:
        await bot.send_message(chat_id, f"EUR/USD: {round(eur_usd_quote, 3)}")


async def send_gbp_eur_quote(bot: TelegramBot, chat_ids: List[int]):
    gbp_eur_quote = get_fx_quote("GBP", "EUR")
    for chat_id in chat_ids:
        await bot.send_message(chat_id, f"GBP/EUR: {round(gbp_eur_quote, 3)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    query_data = query.data

    if query_data == "GPT3":
        await query.message.reply_text("Send me a message to get a GPT-3 response.")
    elif query_data == "GPT4":
        await query.message.reply_text("Send me a message to get a GPT-4 response.")
    elif query_data == "Summary":
        await query.message.reply_text("Send me a message to get a summary.")
    elif query_data == "Blue":
        blue_quotes: Dict[str, float] = get_blue_quote()
        await query.message.reply_text(f"Dolar Blue: {int(blue_quotes.get('value_buy'))} | {int(blue_quotes.get('value_sell'))}")
    elif query_data == "pound":
        gbp_usd_quote = get_fx_quote("GBP", "USD")
        await query.message.reply_text(f"GBP/USD: {round(gbp_usd_quote, 3)}")
    elif query_data == "eurusd":
        eur_usd_quote = get_fx_quote("EUR", "USD")
        await query.message.reply_text(f"EUR/USD: {round(eur_usd_quote, 3)}")
    elif query_data == "eurgbp":
        gbp_eur_quote = get_fx_quote("GBP", "EUR")
        await query.message.reply_text(f"GBP/EUR: {round(gbp_eur_quote, 3)}")
    elif query_data == "mep":
        mep_quote = get_mep_quote()
        await query.message.reply_text(f"Dolar MEP: {mep_quote}")
    else:
        await query.message.reply_text(f"Me no comprender")

async def draw_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        logging.info(f"Drawing buttons for verified user")

        keyboard = [
            [
                InlineKeyboardButton("GPT-3", callback_data="GPT3"),
                InlineKeyboardButton("GPT-4", callback_data="GPT4"),
                InlineKeyboardButton("Summary", callback_data="Summary"),
            ],
            [
                InlineKeyboardButton("Blue", callback_data="Blue"),
                InlineKeyboardButton("Pound", callback_data="pound"),
                InlineKeyboardButton("Mep", callback_data="mep"),
            ],
            [
                InlineKeyboardButton("EUR", callback_data="eurusd"),
                InlineKeyboardButton("EURGBP", callback_data="eurgbp"),
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
    ver_handler = CommandHandler('ver', action_reply_factory(f"Dev Bot running on {os.getenv('THIS_MACHINE')}"))
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)
    callback_handler = CallbackQueryHandler(button_callback)

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    logging.info("Starting DEV bot")
    handlers = [start_handler, ver_handler, echo_handler, callback_handler]
    bot = TelegramBot(token=token, handlers=handlers)

    # Schedule tasks
    schedules = ["10:00", "13:00", "16:00", "19:00"]
    timezone = 'America/Argentina/Buenos_Aires'
    for schedule in schedules:
        bot.schedule_task(send_blue_message, schedule, timezone, [bot, allowed_chat_ids])

    schedules = ["7:00", "12:00", "18:00"]
    timezone = 'America/Argentina/Buenos_Aires'
    for schedule in schedules:
        bot.schedule_task(send_gbp_usd_quote, schedule, timezone, [bot, allowed_chat_ids])

    schedules =  ["10:01", "13:01", "16:01", "19:01"]
    timezone = 'America/Argentina/Buenos_Aires'
    for schedule in schedules:
        bot.schedule_task(send_mep_message, schedule, timezone, [bot, allowed_chat_ids])

    bot.run()


if __name__ == '__main__':
    run_dev_bot()
