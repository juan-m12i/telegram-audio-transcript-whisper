from telegram import Update
from telegram.ext import ContextTypes

from bot.bot_types import ReplyAction


async def action_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="pong")


def action_reply_factory(reply_text: str) -> ReplyAction:
    async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)

    return action
