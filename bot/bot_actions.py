from typing import Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from bot.bot_types import ReplyAction


async def action_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="pong")


async def action_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, don't know how to process that")


async def action_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)


def action_reply_factory(reply_text: str) -> ReplyAction:
    async def action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=reply_text)

    return action
