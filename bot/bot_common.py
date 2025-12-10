import os
import logging
import re
from typing import List, Callable, Coroutine, TypeVar, Any, Dict, Optional
from datetime import datetime

# Try to use zoneinfo (Python 3.9+), fallback to pytz if needed
try:
    from zoneinfo import ZoneInfo
    USE_ZONEINFO = True
except ImportError:
    USE_ZONEINFO = False

# Always try to import pytz as fallback (needed even when zoneinfo is available but tzdata is missing)
try:
    import pytz
except ImportError:
    if not USE_ZONEINFO:
        raise ImportError("Either zoneinfo (Python 3.9+) or pytz is required for timezone support")

import asyncio
from collections import deque
from datetime import datetime, timedelta
#from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, ContextTypes, Application
from telegram import Update, Bot
from telegram.error import NetworkError, TimedOut

from bot.bot_lookup import bots_lookup
from bot.bot_types import ReplyAction, Condition

load_dotenv()  # Python module to load environment variables from a .env file


class TokenSanitizingFilter(logging.Filter):
    """Logging filter that sanitizes Telegram bot API tokens in log messages."""
    
    # Pattern to match bot tokens in URLs: bot<BOT_ID>:<TOKEN>
    # Example: bot5863831530:AAGwypCaB7Zux6S7LeepCTWjYqWJOG1vl6Y
    TOKEN_PATTERN = re.compile(r'bot(\d+):([A-Za-z0-9_-]+)')
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Sanitize log record message by obfuscating bot tokens."""
        try:
            # Sanitize the message components before formatting
            # If msg is a string, sanitize it directly
            if isinstance(record.msg, str):
                record.msg = self._sanitize_message(record.msg)
            # If msg has format placeholders and args, sanitize the args
            elif record.args:
                # Sanitize string arguments
                sanitized_args = tuple(
                    self._sanitize_message(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
                record.args = sanitized_args
            # If msg is not a string and has no args, try to sanitize msg as string
            else:
                record.msg = self._sanitize_message(str(record.msg))
        except Exception:
            # If sanitization fails, don't break logging - just pass through
            pass
        
        return True
    
    def _sanitize_message(self, message: str) -> str:
        """Replace bot tokens in message with obfuscated fingerprints."""
        def replace_token(match):
            bot_id = match.group(1)
            token = match.group(2)
            # Create fingerprint: first 4 chars + .. + last 4 chars
            fingerprint = f"{token[:4]}..{token[-4:]}"
            # Use bot_lookup to get bot name if available
            bot_name = bots_lookup.get(fingerprint, "")
            if bot_name:
                return f"bot{bot_id}:{fingerprint} ({bot_name})"
            return f"bot{bot_id}:{fingerprint}"
        
        return self.TOKEN_PATTERN.sub(replace_token, message)


# Configure logging (native python library)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Reduce verbosity of third-party libraries
# Set httpx, httpcore, and telegram loggers to WARNING to avoid spam
httpx_logger = logging.getLogger("httpx")
httpcore_logger = logging.getLogger("httpcore")
telegram_logger = logging.getLogger("telegram")
httpx_logger.setLevel(logging.WARNING)
httpcore_logger.setLevel(logging.WARNING)
telegram_logger.setLevel(logging.WARNING)

# Apply token sanitizing filter to httpx and httpcore loggers
# This will sanitize tokens in all log messages from these libraries
token_filter = TokenSanitizingFilter()
httpx_logger.addFilter(token_filter)
httpcore_logger.addFilter(token_filter)
# Also add filter to any existing handlers
for handler in httpx_logger.handlers:
    handler.addFilter(token_filter)
for handler in httpcore_logger.handlers:
    handler.addFilter(token_filter)

allowed_chat_ids: List[int] = [int(chat_id) for chat_id in (os.getenv('ALLOWED_CHAT_IDS') or '').split(',') if chat_id.strip()]
chat_ids_report: List[int] = [int(chat_id) for chat_id in (os.getenv('STARTUP_CHAT_IDS_REPORT') or '').split(',') if chat_id.strip()]

# Default timezone: Argentina (GMT-3)
# Can be overridden via TIMEZONE environment variable (e.g., "America/Argentina/Buenos_Aires", "America/New_York", etc.)
DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
TIMEZONE_NAME = os.getenv('TIMEZONE', DEFAULT_TIMEZONE)


def _get_timezone(timezone_name: str = None):
    """Get timezone object for the specified timezone name.
    
    Args:
        timezone_name: Timezone name (e.g., "America/Argentina/Buenos_Aires"). 
                      If None, uses TIMEZONE env var or DEFAULT_TIMEZONE.
    
    Returns:
        Timezone object (ZoneInfo or pytz timezone)
    """
    if timezone_name is None:
        timezone_name = TIMEZONE_NAME
    
    if USE_ZONEINFO:
        # Python 3.9+ with zoneinfo
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            # Fallback to pytz if zoneinfo fails (e.g., tzdata missing on minimal systems)
            # This catches ZoneInfoNotFoundError when tzdata database is absent
            return pytz.timezone(timezone_name)
    else:
        # Fallback to pytz
        return pytz.timezone(timezone_name)


def get_local_datetime(timezone_name: str = None) -> datetime:
    """Get current datetime in the configured timezone.
    
    Args:
        timezone_name: Optional timezone name override. If None, uses TIMEZONE env var or DEFAULT_TIMEZONE.
    
    Returns:
        datetime: Current datetime in the specified timezone
    """
    tz = _get_timezone(timezone_name)
    if USE_ZONEINFO:
        # zoneinfo returns timezone-aware datetime
        return datetime.now(tz)
    else:
        # pytz requires localize
        return pytz.UTC.localize(datetime.utcnow()).astimezone(tz)


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


class NetworkErrorTracker:
    """Tracks network errors to detect persistent connectivity issues.
    
    Logs transient errors at WARNING level, escalates to ERROR if too many
    errors occur within the time window (indicating a real problem).
    """
    
    def __init__(
        self,
        error_threshold: int = 5,
        time_window_minutes: int = 5,
        bot_name: str = "Unknown Bot"
    ):
        """Initialize the error tracker.
        
        Args:
            error_threshold: Number of errors within time window to trigger ERROR level
            time_window_minutes: Time window in minutes for counting errors
            bot_name: Name of the bot for logging context
        """
        self.error_threshold = error_threshold
        self.time_window = timedelta(minutes=time_window_minutes)
        self.bot_name = bot_name
        self.recent_errors: deque = deque()
    
    def _cleanup_old_errors(self):
        """Remove errors older than the time window."""
        now = datetime.now()
        while self.recent_errors and (now - self.recent_errors[0]) > self.time_window:
            self.recent_errors.popleft()
    
    def record_error(self) -> int:
        """Record an error and return the count of recent errors."""
        now = datetime.now()
        self.recent_errors.append(now)
        self._cleanup_old_errors()
        return len(self.recent_errors)
    
    def is_persistent(self) -> bool:
        """Check if errors are persistent (exceed threshold)."""
        self._cleanup_old_errors()
        return len(self.recent_errors) >= self.error_threshold


def create_error_handler(bot_name: str = "Unknown Bot"):
    """Create an error handler with its own error tracker.
    
    Args:
        bot_name: Name of the bot for logging context
    
    Returns:
        Async error handler function for telegram bot
    """
    tracker = NetworkErrorTracker(
        error_threshold=5,
        time_window_minutes=5,
        bot_name=bot_name
    )
    
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors from the telegram bot.
        
        - Network errors (transient): Log at WARNING level
        - Network errors (persistent): Escalate to ERROR level
        - Other errors: Always log at ERROR level
        """
        error = context.error
        
        # Check if it's a network-related error
        is_network_error = isinstance(error, (NetworkError, TimedOut))
        
        if is_network_error:
            error_count = tracker.record_error()
            
            if tracker.is_persistent():
                # Too many errors in short time - this is a real problem
                logging.error(
                    f"[{tracker.bot_name}] PERSISTENT network issues detected! "
                    f"{error_count} errors in last {tracker.time_window.total_seconds() / 60:.0f} minutes. "
                    f"Error: {type(error).__name__}: {error}"
                )
            else:
                # Transient error - log at INFO (expected, auto-recovers, no alert needed)
                logging.info(
                    f"[{tracker.bot_name}] Transient network error "
                    f"({error_count}/{tracker.error_threshold} in window): "
                    f"{type(error).__name__}: {error}"
                )
        else:
            # Non-network error - always log at ERROR level
            logging.error(
                f"[{tracker.bot_name}] Exception while handling an update: {error}",
                exc_info=context.error
            )
    
    return error_handler

async def send_startup_message(token: str, chat_id: int, message: str):
    bot = Bot(token)
    await bot.send_message(chat_id, message)


def run_telegram_bot(token: str, handlers: List[Handler], scheduled_tasks: Optional[List[Dict[str, Any]]] = None):
    # This comes directly from the telegram bot library
    bot = build_bot(token)

    # The telegram bot manages events to process through handlers:
    # For each handled event group, the relevant function (defined above) will be invoked
    for handler in handlers:
        bot.add_handler(handler)

    # The app will be running constantly checking for new events

    bot_token_fingerprint = f"{token[:4]}..{token[-4:]}"
    bot_name = bots_lookup.get(bot_token_fingerprint, bot_token_fingerprint)
    
    # Add error handler to reduce noise from transient network errors
    bot.add_error_handler(create_error_handler(bot_name))
    
    init_message = f"Running telegram bot {bot_token_fingerprint} - {bot_name} on Machine" \
                   f" {os.environ.get('THIS_MACHINE')}"
    logging.info(init_message)

    loop = asyncio.get_event_loop()
    # TODO this should print which bot code is running, not where it's hosted
    for chat_id in chat_ids_report:
        loop.run_until_complete(send_startup_message(token, chat_id, f"Running {bot_name} on {os.environ.get('THIS_MACHINE')}"))

    bot.run_polling()


class TelegramBot:
    def __init__(self, token: str, handlers: Optional[List[Any]] = None):
        self.token = token
        if handlers is None:
            handlers = []
        self.handlers: List = handlers
        self.bot = Bot(token)
        self.application = build_bot(token)
        self.scheduler = AsyncIOScheduler()

    def add_handler(self, handler):
        self.handlers.append(handler)

    async def send_message(self, chat_id: int, text: str, **kwargs):
        return await self.bot.send_message(chat_id, text, **kwargs)

    def schedule_task(self, task_func: Callable, schedule: str, timezone: str, args: list):
        hour, minute = schedule.split(':')
        self.scheduler.add_job(task_func, 'cron', args=args, day_of_week='mon-fri', hour=int(hour), minute=int(minute),
                               timezone=timezone)

    def run(self):
        for handler in self.handlers:
            self.application.add_handler(handler)

        bot_token_fingerprint = f"{self.token[:4]}..{self.token[-4:]}"
        bot_name = bots_lookup.get(bot_token_fingerprint, bot_token_fingerprint)
        
        # Add error handler to reduce noise from transient network errors
        self.application.add_error_handler(create_error_handler(bot_name))
        
        init_message = f"Running telegram bot {bot_token_fingerprint} - {bot_name} on Machine" \
                       f" {os.environ.get('THIS_MACHINE')}"
        logging.info(init_message)

        loop = asyncio.get_event_loop()
        for chat_id in chat_ids_report:
            loop.run_until_complete(send_startup_message(self.token, chat_id,
                                                         f"Running {bot_name} on "
                                                         f"{os.environ.get('THIS_MACHINE')}"))

        self.scheduler.start()
        self.application.run_polling()


    def stop(self):
        self.bot.stop_polling()
        self.scheduler.shutdown()