# IMPORTANT: This bot follows a specific structure that has been proven to work reliably.
# Key architectural decisions that MUST be maintained:
# 1. Use python-telegram-bot's built-in job queue instead of external schedulers
# 2. Keep the TelegramBot class simple with initialization and run methods
# 3. Use the application's job queue for all scheduled tasks
# 4. Avoid mixing async/await with synchronous code
# 5. Use context.bot instead of creating separate bot instances
#
# DO NOT modify this structure without careful consideration!

import os
import sys
import logging
from datetime import datetime, timedelta
import httpx
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv, dotenv_values
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
import uuid
import argparse
import pytz  # Add timezone support

load_dotenv()

# Configure root logger to be less verbose
logging.basicConfig(level=logging.WARNING)  # This will affect third-party loggers

# Configure our app logger
logger = logging.getLogger("sleep_tracker_bot")

# Add argument parsing
parser = argparse.ArgumentParser(description='Sleep Tracker Telegram Bot')
parser.add_argument('--local', action='store_true', help='Use localhost backend')
parser.add_argument('--debug', action='store_true', help='Enable debug logging')
args = parser.parse_args()

# Configure logging based on command line argument
log_level = logging.DEBUG if args.debug else logging.INFO
logger.setLevel(log_level)
logger.info(f"Log level set to: {logging.getLevelName(log_level)}")

# Create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(console_handler)

# Silence some particularly noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# Set the backend URL based on argument
BACKEND_URL = 'http://localhost:8080' if args.local else 'https://sleep-tracker-136994214879.us-central1.run.app'
backend_type = "LOCAL" if args.local else "REMOTE"
logger.info(f"Using {backend_type} backend at: {BACKEND_URL}")

# Set timezone
TIMEZONE = 'America/Argentina/Buenos_Aires'
timezone = pytz.timezone(TIMEZONE)
logger.info(f"Using timezone: {TIMEZONE}")

# Load .env file values first
dot_env_vars = dotenv_values(".env")

# Get environment
env = os.getenv('ENVIRONMENT', 'dev').lower()
logger.info(f"Starting bot in {env.upper()} environment")

# Try .env first, then fall back to system environment
allowed_chat_ids = [
    int(id) for id in (
        dot_env_vars.get('ALLOWED_CHAT_IDS') or 
        os.getenv('ALLOWED_CHAT_IDS', '')
    ).split(',')
]

# Get bot token with environment-specific fallback
bot_token = (
    dot_env_vars.get(f'TELEGRAM_BOT_TOKEN_{env.upper()}') or
    dot_env_vars.get('TELEGRAM_BOT_TOKEN') or
    os.getenv('TELEGRAM_BOT_TOKEN')
)

if not bot_token:
    logger.error("TELEGRAM_BOT_TOKEN not found in .env or environment variables")
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

logger.info(f"Starting bot with log level: {logging.getLevelName(log_level)}")
logger.debug(f"Backend URL: {BACKEND_URL}")
logger.debug(f"Allowed chat IDs: {allowed_chat_ids}")

# Memory cache for offline operation
class BotMemoryCache:
    def __init__(self):
        self.pending_entries: List[Dict[str, Any]] = []
        self.last_known_entries: List[Dict[str, Any]] = []
        self.is_backend_available: bool = False
    
    def add_pending_entry(self, entry: Dict[str, Any]):
        """Add an entry to pending when backend is unavailable"""
        self.pending_entries.append(entry)
        logger.debug(f"Added entry to pending cache. Total pending: {len(self.pending_entries)}")
    
    def update_last_known_entries(self, entries: List[Dict[str, Any]]):
        """Update the cache of last known entries from backend"""
        self.last_known_entries = entries
        logger.debug(f"Updated last known entries cache. Total entries: {len(entries)}")
    
    def get_combined_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get combined history of pending and last known entries"""
        # Combine and sort by timestamp, newest first
        all_entries = self.pending_entries + self.last_known_entries
        sorted_entries = sorted(all_entries, key=lambda x: x['timestamp'], reverse=True)
        return sorted_entries[:limit]
    
    def clear_pending(self):
        """Clear pending entries after they've been synced"""
        count = len(self.pending_entries)
        self.pending_entries = []
        logger.debug(f"Cleared {count} pending entries")

# Initialize the memory cache as a global variable
bot_memory = BotMemoryCache()

def is_allowed_user(update: Update) -> bool:
    """Check if the user is allowed to use the bot"""
    try:
        # Get chat_id from either callback query or regular message
        if update.callback_query:
            chat_id = update.callback_query.message.chat_id
        elif update.message:
            chat_id = update.message.chat_id
        else:
            logger.error("Could not get chat_id from update")
            return False
        
        allowed = chat_id in allowed_chat_ids
        logger.debug(f"Chat ID {chat_id} allowed: {allowed}")
        return allowed
        
    except Exception as e:
        logger.error(f"Error checking user permission: {e}")
        return False

def get_start_menu_keyboard():
    """Helper function to create the start menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("📝 Check In", callback_data="menu_check"),
            InlineKeyboardButton("📊 History", callback_data="menu_history")
        ],
        [
            InlineKeyboardButton("🗑️ Delete Last Log", callback_data="menu_delete"),
            InlineKeyboardButton("🔄 Sync", callback_data="menu_sync")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update):
        return
    
    reply_markup = get_start_menu_keyboard()
    await update.message.reply_text(
        "Welcome to Sleep Tracker! Choose an option:",
        reply_markup=reply_markup
    )

async def show_start_menu(message):
    """Helper function to show the start menu"""
    reply_markup = get_start_menu_keyboard()
    await message.reply_text(
        "What would you like to do next?",
        reply_markup=reply_markup
    )

async def send_rating_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, checkin_type: str):
    keyboard = [
        [
            InlineKeyboardButton("1 (Very Alert)", callback_data=f"1_{checkin_type}"),
            InlineKeyboardButton("2 (Alert)", callback_data=f"2_{checkin_type}"),
        ],
        [
            InlineKeyboardButton("3 (Drowsy)", callback_data=f"3_{checkin_type}"),
            InlineKeyboardButton("4 (Very Drowsy)", callback_data=f"4_{checkin_type}"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Handle both Message and CallbackQuery cases
    if isinstance(update, Update):
        await update.message.reply_text("How drowsy do you feel right now?", reply_markup=reply_markup)
    else:  # Message object directly
        await update.reply_text("How drowsy do you feel right now?", reply_markup=reply_markup)

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update):
        return
    logger.debug(f"Starting check-in for user {update.effective_chat.id}")
    await send_rating_keyboard(update, context, "on-demand")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update):
        return

    query = update.callback_query
    await query.answer()
    
    # Handle menu actions
    if query.data.startswith("menu_"):
        action = query.data.split("_")[1]
        if action == "check":
            await send_rating_keyboard(query.message, context, "on-demand")
            return
        elif action == "history":
            await history(update, context)
            return
        elif action == "sync":
            await sync_command(update, context)
            return
        elif action == "delete":
            # Show delete confirmation
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, delete", callback_data="delete_confirm"),
                    InlineKeyboardButton("❌ No, cancel", callback_data="delete_cancel")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Are you sure you want to delete the last log entry?",
                reply_markup=reply_markup
            )
            return
    
    # Handle delete confirmation
    if query.data.startswith("delete_"):
        action = query.data.split("_")[1]
        if action == "confirm":
            try:
                async with httpx.AsyncClient() as client:
                    logger.debug("Attempting to delete last entry")
                    response = await client.delete(f"{BACKEND_URL}/delete-last-entry")
                    if response.status_code == 200:
                        deleted_entry = response.json().get("deleted_entry", {})
                        timestamp = deleted_entry.get("timestamp", "unknown time")
                        checkin_type = deleted_entry.get("checkin_type", "unknown type")
                        rating = deleted_entry.get("rating", "unknown rating")
                        await query.edit_message_text(
                            f"✅ Successfully deleted entry:\n"
                            f"Time: {timestamp}\n"
                            f"Type: {checkin_type}\n"
                            f"Rating: {rating}"
                        )
                        # Show start menu after successful deletion
                        await show_start_menu(query.message)
                    else:
                        error_detail = response.json().get("detail", "Unknown error")
                        await query.edit_message_text(f"❌ Failed to delete last entry: {error_detail}")
                        # Show start menu after error
                        await show_start_menu(query.message)
            except Exception as e:
                logger.error(f"Error deleting last entry: {e}")
                await query.edit_message_text("❌ Error occurred while deleting entry.")
                # Show start menu after error
                await show_start_menu(query.message)
        else:
            await query.edit_message_text("Operation cancelled.")
            # Show start menu after cancellation
            await show_start_menu(query.message)
        return
    
    # Handle flush confirmation
    if query.data.startswith("flush_"):
        if query.data == "flush_confirm":
            count = len(bot_memory.pending_entries)
            bot_memory.clear_pending()
            await query.edit_message_text(f"✅ Cleared {count} pending entries from memory.")
        else:
            await query.edit_message_text("Operation cancelled. Pending entries preserved.")
        return
    
    # Parse the callback data for ratings
    data = query.data.split('_')
    if len(data) != 2:
        return
    
    rating = int(data[0])
    checkin_type = data[1]
    
    # Create entry data with timezone-aware timestamp in Buenos Aires time
    entry = {
        'id': str(uuid.uuid4()),
        'timestamp': datetime.now(timezone).isoformat(),  # Already in Buenos Aires time
        'checkin_type': checkin_type,
        'rating': rating,
        'notes': None,
        'client': 'telegram'
    }
    
    # Store the entry ID for potential note addition
    context.user_data['last_entry_id'] = entry['id']
    
    try:
        if bot_memory.is_backend_available:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BACKEND_URL}/submit", json=entry)
                if response.status_code != 200:
                    raise Exception(f"Backend error: {response.status_code}")
                logger.debug("Entry submitted to backend successfully")
        else:
            # Store in memory if backend is unavailable
            bot_memory.add_pending_entry(entry)
            logger.debug("Entry stored in memory cache")
        
        await query.edit_message_text(
            f"Recorded {checkin_type} drowsiness level: {rating}\n"
            "You can add notes to this entry using:\n"
            "/note your note text"
        )
        
    except Exception as e:
        logger.error(f"Error submitting entry: {e}")
        # Always store in memory if submission fails
        bot_memory.add_pending_entry(entry)
        await query.edit_message_text(
            f"Recorded {checkin_type} drowsiness level: {rating} (stored offline)\n"
            "Entry will be synced when backend is available.\n"
            "You can add notes using:\n"
            "/note your note text"
        )

async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_user(update):
        return
        
    if len(context.args) == 0:
        await update.message.reply_text(
            "Please provide the note text after the command.\n"
            "Example: /note Feeling tired after lunch"
        )
        return
        
    if 'last_entry_id' not in context.user_data:
        await update.message.reply_text(
            "No recent entry found to add notes to.\n"
            "Please submit a new entry first with /check"
        )
        return
    
    # Get the note text from command arguments
    note_text = ' '.join(context.args)
    entry_id = context.user_data['last_entry_id']
    
    logger.debug(f"Adding note to entry {entry_id}: {note_text}")
    
    # Get the current entry data
    async with httpx.AsyncClient() as client:
        try:
            # First, get the entry data from history
            response = await client.get(f"{BACKEND_URL}/history?limit=10")
            if response.status_code != 200:
                raise Exception("Failed to fetch entry data")
            
            entries = response.json()
            entry = next((e for e in entries if e['id'] == entry_id), None)
            
            if not entry:
                raise Exception("Entry not found")
            
            # Update the entry with the new note
            entry['notes'] = note_text
            
            # Submit the update
            update_response = await client.put(
                f"{BACKEND_URL}/entry/{entry_id}",
                json=entry
            )
            
            if update_response.status_code == 200:
                await update.message.reply_text("Note added successfully!")
            else:
                logger.error(f"Backend error response: {update_response.text}")
                await update.message.reply_text("Error adding note. Please try again.")
                
        except Exception as e:
            logger.error(f"Error adding note: {e}")
            await update.message.reply_text("Error adding note. Please try again.")

async def scheduled_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send scheduled reminders to all allowed users"""
    # Get the checkin type from job data
    checkin_type = context.job.data
    
    logger.info(f"Sending {checkin_type} reminders")
    for chat_id in allowed_chat_ids:
        try:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=f"Time for your {checkin_type} check-in!"
            )
            # Create a fake update object to reuse send_rating_keyboard
            fake_update = Update(0, message)
            await send_rating_keyboard(fake_update, context, checkin_type)
            logger.debug(f"Sent {checkin_type} reminder to chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send {checkin_type} reminder to {chat_id}: {e}")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle both Update and CallbackQuery objects
    if hasattr(update, 'callback_query'):
        if not is_allowed_user(update):
            return
        chat_id = update.callback_query.message.chat_id
        message = update.callback_query.message
    else:
        if not is_allowed_user(update):
            return
        chat_id = update.effective_chat.id
        message = update.message
        
    logger.debug("Fetching history")
    
    try:
        if bot_memory.is_backend_available:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/history?limit=5")
                if response.status_code == 200:
                    entries = response.json()
                    bot_memory.update_last_known_entries(entries)
                else:
                    raise Exception(f"Backend error: {response.status_code}")
        
        # Get combined history from memory
        entries = bot_memory.get_combined_history(limit=5)
        
        if not entries:
            if hasattr(update, 'callback_query'):
                await update.callback_query.edit_message_text("No entries found.")
            else:
                await message.reply_text("No entries found.")
            # Show start menu after showing no entries
            await show_start_menu(message)
            return
            
        message_text = "Recent entries:\n\n"
        for entry in entries:
            # Add a 🔄 indicator for pending entries
            status = "🔄 " if entry in bot_memory.pending_entries else ""
            message_text += (
                f"{status}📅 {entry['timestamp']}\n"
                f"Type: {entry['checkin_type']}\n"
                f"Rating: {entry['rating']}\n"
                f"Notes: {entry['notes'] or 'N/A'}\n\n"
            )
        
        if bot_memory.pending_entries:
            message_text += f"\n🔄 {len(bot_memory.pending_entries)} entries pending sync"
            
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(message_text)
            # Show start menu in a new message after showing history
            await show_start_menu(message)
        else:
            await message.reply_text(message_text)
            # Show start menu after showing history
            await show_start_menu(message)
            
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        # If we can't fetch from backend, just show what we have in memory
        entries = bot_memory.get_combined_history(limit=5)
        if not entries:
            error_text = "⚠️ Backend is unavailable and no entries in local cache."
        else:
            error_text = "⚠️ Backend is unavailable. Showing cached entries:\n\n"
            for entry in entries:
                status = "🔄 " if entry in bot_memory.pending_entries else ""
                error_text += (
                    f"{status}📅 {entry['timestamp']}\n"
                    f"Type: {entry['checkin_type']}\n"
                    f"Rating: {entry['rating']}\n"
                    f"Notes: {entry['notes'] or 'N/A'}\n\n"
                )
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(error_text)
        else:
            await message.reply_text(error_text)
        # Show start menu after error
        await show_start_menu(message)

async def show_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current state of the memory cache"""
    if not is_allowed_user(update):
        return
        
    message = "🧠 Memory Cache Status:\n\n"
    
    # Backend status
    status = "🟢 Online" if bot_memory.is_backend_available else "🔴 Offline"
    message += f"Backend: {status}\n\n"
    
    # Pending entries
    message += f"Pending Entries: {len(bot_memory.pending_entries)}\n"
    if bot_memory.pending_entries:
        message += "Latest pending entries:\n"
        for entry in bot_memory.pending_entries[-3:]:  # Show last 3
            message += f"- {entry['timestamp']}: {entry['checkin_type']}, rating {entry['rating']}\n"
    
    # Cached entries
    message += f"\nCached Entries: {len(bot_memory.last_known_entries)}\n"
    if bot_memory.last_known_entries:
        message += "Latest cached entries:\n"
        for entry in bot_memory.last_known_entries[:3]:  # Show first 3
            message += f"- {entry['timestamp']}: {entry['checkin_type']}, rating {entry['rating']}\n"
    
    await update.message.reply_text(message)

async def flush_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear pending entries from memory"""
    if not is_allowed_user(update):
        return
        
    count = len(bot_memory.pending_entries)
    if count == 0:
        await update.message.reply_text("No pending entries to flush.")
        return
        
    # Ask for confirmation
    keyboard = [
        [
            InlineKeyboardButton("Yes, delete all", callback_data="flush_confirm"),
            InlineKeyboardButton("No, keep them", callback_data="flush_cancel"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚠️ Are you sure you want to delete {count} pending entries?\n"
        "They will be permanently lost and won't sync to the backend.",
        reply_markup=reply_markup
    )

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger synchronization of pending entries"""
    if not is_allowed_user(update):
        return
        
    if not bot_memory.pending_entries:
        await update.message.reply_text("No pending entries to sync.")
        return
        
    if not bot_memory.is_backend_available:
        await update.message.reply_text(
            "⚠️ Backend is currently offline.\n"
            f"There are {len(bot_memory.pending_entries)} entries pending sync.\n"
            "They will be automatically synced when the backend becomes available."
        )
        return
        
    # Show sync in progress message
    message = await update.message.reply_text(
        f"🔄 Attempting to sync {len(bot_memory.pending_entries)} entries..."
    )
    
    # Try to sync
    async with httpx.AsyncClient() as client:
        synced = 0
        failed = 0
        
        for entry in bot_memory.pending_entries[:]:  # Create a copy to iterate
            try:
                response = await client.post(f"{BACKEND_URL}/submit", json=entry)
                if response.status_code == 200:
                    bot_memory.pending_entries.remove(entry)
                    synced += 1
                    logger.debug(f"Successfully synced entry from {entry['timestamp']}")
                else:
                    failed += 1
                    logger.error(f"Failed to sync entry with status {response.status_code}")
            except Exception as e:
                failed += 1
                logger.error(f"Failed to sync entry: {e}")
        
        # Update the message with results
        if failed == 0:
            await message.edit_text(f"✅ Successfully synced {synced} entries!")
        else:
            await message.edit_text(
                f"📊 Sync results:\n"
                f"✅ {synced} entries synced successfully\n"
                f"❌ {failed} entries failed to sync\n\n"
                f"Remaining pending entries: {len(bot_memory.pending_entries)}"
            )

class TelegramBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler('start', start))
        self.application.add_handler(CommandHandler('check', check_command))
        self.application.add_handler(CommandHandler('history', history))
        self.application.add_handler(CommandHandler('note', add_note))
        self.application.add_handler(CallbackQueryHandler(button_callback))
        self.application.add_handler(CommandHandler('memory', show_memory))
        self.application.add_handler(CommandHandler('sync', sync_command))
        self.application.add_handler(CommandHandler('flush', flush_memory))

        # Set up job queue for reminders
        job_queue = self.application.job_queue
        
        # Schedule daily reminders with timezone
        morning_time = timezone.localize(datetime.strptime('07:30', '%H:%M')).time()
        afternoon_time = timezone.localize(datetime.strptime('14:39', '%H:%M')).time()
        
        # Schedule reminders with correct data
        job_queue.run_daily(
            scheduled_reminder,
            time=morning_time,
            data="morning"  # Pass string directly
        )
        job_queue.run_daily(
            scheduled_reminder,
            time=afternoon_time,
            data="afternoon"  # Pass string directly
        )
        
        logger.info(f"Scheduled morning reminder for {morning_time}")
        logger.info(f"Scheduled afternoon reminder for {afternoon_time}")

        # Send startup notification and schedule periodic backend checks
        job_queue.run_once(self.send_startup_notification, when=1)
        job_queue.run_repeating(self.check_backend_health, interval=60, first=10)

    async def check_backend_health(self, context: ContextTypes.DEFAULT_TYPE):
        """Periodically check backend health and try to sync pending entries"""
        is_available = await self.check_backend()
        if is_available != bot_memory.is_backend_available:
            bot_memory.is_backend_available = is_available
            status = "🟢 Backend is now available" if is_available else "🔴 Backend is currently unavailable"
            
            # Notify users of status change
            for chat_id in allowed_chat_ids:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=status)
                except Exception as e:
                    logger.error(f"Failed to send status update to {chat_id}: {e}")
            
            # If backend is back online, try to sync pending entries
            if is_available and bot_memory.pending_entries:
                await self.sync_pending_entries(context)

    async def sync_pending_entries(self, context: ContextTypes.DEFAULT_TYPE):
        """Try to sync pending entries when backend becomes available"""
        logger.info(f"Attempting to sync {len(bot_memory.pending_entries)} pending entries")
        
        async with httpx.AsyncClient() as client:
            for entry in bot_memory.pending_entries[:]:  # Create a copy to iterate
                try:
                    response = await client.post(f"{BACKEND_URL}/submit", json=entry)
                    if response.status_code == 200:
                        bot_memory.pending_entries.remove(entry)
                        logger.debug(f"Successfully synced entry from {entry['timestamp']}")
                except Exception as e:
                    logger.error(f"Failed to sync entry: {e}")
        
        if not bot_memory.pending_entries:
            for chat_id in allowed_chat_ids:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="✅ All pending entries have been synced to the backend!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send sync completion message to {chat_id}: {e}")

    async def send_startup_notification(self, context: ContextTypes.DEFAULT_TYPE):
        """Send startup notifications to all allowed users"""
        # Check backend first
        backend_ok = await self.check_backend()
        status_msg = "✅ Backend is accessible" if backend_ok else "⚠️ Backend is not accessible"
        
        startup_message = (
            "🤖 Sleep Tracker Bot is now online!\n"
            f"{status_msg}\n"
            "Use /start to see available commands."
        )
        
        for chat_id in allowed_chat_ids:
            try:
                await context.bot.send_message(chat_id=chat_id, text=startup_message)
                logger.info(f"Sent startup notification to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send startup notification to {chat_id}: {e}")

    async def check_backend(self) -> bool:
        """Check if backend is accessible"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/history?limit=1")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Backend check failed: {e}")
            return False

    def run(self):
        """Start the bot"""
        logger.info("Starting bot...")
        self.application.run_polling(drop_pending_updates=True)

def main():
    bot = TelegramBot(bot_token)
    bot.run()

if __name__ == "__main__":
    main() 