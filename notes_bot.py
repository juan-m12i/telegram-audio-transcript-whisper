import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler
from adapters.notion_adapter import NotionAdapter
from bot_actions import action_ping
from bot_common import bot_start, run_telegram_bot, reply_builder
from bot_handler_factory import condition_ping, condition_catch_all

load_dotenv()  # Python module to load environment variables from a .env file


allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(
    ',')]  # Pythonic way of creating a list, behaves like a loop


my_notion = NotionAdapter(os.getenv("NOTION_TOKEN"))

async def action_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        my_notion.add_block(parent_id=os.getenv("NOTION_PAGE_ID"), text=update.message.text, block_type="bulleted_list_item")
        await update.message.reply_text("Note stored")
    except Exception as e:
        logging.error(f"Error while adding block to Notion: {e}")
        await update.message.reply_text(f"Failed to store note: {e}")


reply = reply_builder({
    condition_ping: action_ping,
    condition_catch_all: action_notes,
})



def run_notes_bot():

    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    start_command = bot_start("Welcome, I'd love to help with your notes")
    start_handler = CommandHandler('start', start_command)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)

    run_telegram_bot(os.getenv('TELEGRAM_BOT_TOKEN'), [start_handler, echo_handler])


if __name__ == '__main__':
    run_notes_bot()
