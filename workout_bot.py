import os
import logging
from typing import List
from dotenv import load_dotenv

# Load workout_bot.env FIRST, before importing bot_common which loads .env by default
load_dotenv('workout_bot.env', override=True)

from telegram import Update, ReactionTypeEmoji
from telegram.ext import filters, MessageHandler, ContextTypes, CommandHandler
from adapters.api_adapter import ApiAdapter
from bot.bot_actions import action_ping, action_reply_factory
from bot.bot_common import bot_start, run_telegram_bot, get_local_datetime

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in os.getenv('ALLOWED_CHAT_IDS').split(',')]

# Initialize API adapter
storage_adapter = ApiAdapter()


async def action_save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle both new messages and edited messages.
    
    The API adapter handles idempotency - if a message_id already exists,
    it updates the note; otherwise, it creates a new one.
    """
    if update.effective_chat.id not in allowed_chat_ids:
        return
    
    try:
        # Determine if this is an edit or new message
        is_edit = update.edited_message is not None
        message = update.edited_message if is_edit else update.message
        
        if not message or not message.text:
            return
        
        # Handle "ping" messages - respond with "pong" without saving to database
        if message.text.lower().strip() == "ping":
            await action_ping(update, context)
            return
        
        # Get timestamps
        timestamp = get_local_datetime()
        
        # For edits, use the original message date as date_created
        # For new messages, use current timestamp for both
        if is_edit:
            # Edited messages have both date (original) and edit_date (when edited)
            date_created = message.date
            last_updated = timestamp
        else:
            date_created = timestamp
            last_updated = timestamp
        
        # Save note via API adapter
        result = await storage_adapter.save_note(
            message_id=str(message.message_id),
            text=message.text,
            date_created=date_created,
            last_updated=last_updated,
            chat_id=update.effective_chat.id
        )
        
        # React to the message instead of sending a reply
        # Use simple emojis that are definitely supported: 👍 for created, ❤️ for updated
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
        logging.error(f"Error saving note: {e}", exc_info=True)
        # Don't send error message to user, just log it as requested


def run_workout_bot():
    """Run the workout notes bot."""
    start_command = bot_start("Welcome! Send me your workout notes. Edit messages to update them.")
    start_handler = CommandHandler('start', start_command)
    ver_handler = CommandHandler('ver', action_reply_factory("Workout Bot"))
    ping_handler = CommandHandler('ping', action_ping)
    
    # Handle text messages (both new and edited)
    # Note: MessageHandler handles regular messages, and we check for edited_message in the handler
    message_handler = MessageHandler(
        filters.TEXT & (~filters.COMMAND),
        action_save_note
    )
    
    # For edited messages, we need to add a handler that checks update.edited_message
    # In python-telegram-bot v20, edited messages come as separate updates
    # We'll handle them in the same handler by checking update.edited_message
    from telegram.ext import BaseHandler
    
    class EditedMessageHandler(BaseHandler):
        def __init__(self, callback):
            super().__init__(callback)
        
        def check_update(self, update):
            return update.edited_message is not None and update.edited_message.text and not update.edited_message.text.startswith('/')
    
    edited_message_handler = EditedMessageHandler(action_save_note)
    
    logging.info("Starting Workout bot")
    run_telegram_bot(
        os.getenv('TELEGRAM_BOT_TOKEN'),
        [start_handler, ver_handler, ping_handler, message_handler, edited_message_handler]
    )


if __name__ == '__main__':
    run_workout_bot()

