from typing import Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

ReplyAction = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine]