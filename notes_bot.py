import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, ContextTypes, CommandHandler
from adapters.notion_adapter import NotionAdapter
from common_bot import allowed_user, build_bot, add_handlers, bot_start

load_dotenv()  # Python module to load environment variables from a .env file


allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(
    ',')]  # Pythonic way of creating a list, behaves like a loop


my_notion = NotionAdapter(os.getenv("NOTION_TOKEN"))
NOTION_PAGE_ID = "20fe25981f634cea8d90098dddb543a0"


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed_user(update):
        logging.info(f"Replying message from verified user")
        received_message_text = update.message.text
        if received_message_text == 'ping':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="pong")
        else:
            try:
                my_notion.add_block(parent_id=NOTION_PAGE_ID, text=received_message_text, block_type="bulleted_list_item")
                # reply with success message
                await update.message.reply_text("Note stored")
            except Exception as e:
                logging.error(f"Error while adding block to Notion: {e}")
                await update.message.reply_text(f"Failed to store note: {e}")




# Remove the temporary audio file


if __name__ == '__main__':
    my_notion.add_block(parent_id=NOTION_PAGE_ID, text="Hello Worlds", block_type="bulleted_list_item")

    # This comes directly from the telegram bot library
    bot = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    start_command = bot_start("Welcome, I'd love to help with your notes")
    start_handler = CommandHandler('start', start_command)
    echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), reply)

    bot.add_handler(start_handler)
    bot.add_handler(echo_handler)

    # The app will be running constantly checking for new events
    bot.run_polling()
