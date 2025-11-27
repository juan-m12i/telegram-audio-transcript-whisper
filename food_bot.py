import os
import logging
from typing import List
from dotenv import load_dotenv

# Load food_bot.env FIRST, before importing bot_common which loads .env by default
load_dotenv('food_bot.env', override=True)

from telegram import Update, ReactionTypeEmoji
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler
from adapters.api_adapter import ApiAdapter
from bot.bot_actions import action_ping, action_reply_factory
from bot.bot_common import bot_start, run_telegram_bot, get_local_datetime

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]

# Initialize API adapter
api_adapter = ApiAdapter()


async def action_save_food_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle both new messages and edited messages for food logging.
    
    The API adapter handles idempotency - if a message_id already exists,
    it updates the log; otherwise, it creates a new one.
    """
    if update.effective_chat.id not in allowed_chat_ids:
        return
    
    try:
        # Determine if this is an edit or new message
        is_edit = update.edited_message is not None
        message = update.edited_message if is_edit else update.message
        
        if not message or not message.text:
            return
        
        # Save food log via API adapter
        result = await api_adapter.save_food_log(
            message_id=str(message.message_id),
            text=message.text,
            chat_id=update.effective_chat.id
        )
        
        # React to the message instead of sending a reply
        # Use simple emojis: 👍 for created, ❤️ for updated
        status_emoji = "👍" if result["status"] == "created" else "❤️"
        try:
            # If this is an update, clear previous reaction first, then set new one
            if result["status"] == "updated":
                try:
                    await context.bot.set_message_reaction(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        reaction=None  # Clear existing reactions first
                    )
                except Exception:
                    pass  # Ignore errors when clearing
            
            # Set the new reaction
            reaction = ReactionTypeEmoji(status_emoji)
            await context.bot.set_message_reaction(
                chat_id=update.effective_chat.id,
                message_id=message.message_id,
                reaction=reaction  # Pass directly, not in a list
            )
        except Exception as reaction_error:
            # If reaction fails, try with a list (some versions might need it)
            logging.warning(f"Failed to set reaction {status_emoji} directly, trying as list: {reaction_error}")
            try:
                reaction = ReactionTypeEmoji(status_emoji)
                await context.bot.set_message_reaction(
                    chat_id=update.effective_chat.id,
                    message_id=message.message_id,
                    reaction=[reaction]
                )
            except Exception as list_error:
                # If that also fails, try with a simple string emoji
                logging.warning(f"Failed with list too, trying string emoji: {list_error}")
                try:
                    await context.bot.set_message_reaction(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        reaction=status_emoji  # Try passing emoji as string
                    )
                except Exception:
                    # If reactions don't work at all, just log it
                    logging.error(f"Could not set any reaction. Direct: {reaction_error}, List: {list_error}")
        
    except Exception as e:
        logging.error(f"Error saving food log: {e}", exc_info=True)
        # Don't send error message to user, just log it


def run_food_bot():
    """Run the food log bot."""
    start_command = bot_start("Welcome! Send me your food logs. Edit messages to update them.")
    start_handler = CommandHandler('start', start_command)
    ver_handler = CommandHandler('ver', action_reply_factory("Food Bot"))
    
    # Handle text messages (both new and edited)
    message_handler = MessageHandler(
        filters.TEXT & (~filters.COMMAND),
        action_save_food_log
    )
    
    # For edited messages, we need a handler that checks update.edited_message
    from telegram.ext import BaseHandler
    
    class EditedMessageHandler(BaseHandler):
        def __init__(self, callback):
            super().__init__(callback)
        
        def check_update(self, update):
            return update.edited_message is not None and update.edited_message.text and not update.edited_message.text.startswith('/')
    
    edited_message_handler = EditedMessageHandler(action_save_food_log)
    
    logging.info("Starting Food bot")
    run_telegram_bot(
        os.getenv('TELEGRAM_BOT_TOKEN'),
        [start_handler, ver_handler, message_handler, edited_message_handler]
    )


if __name__ == '__main__':
    run_food_bot()

