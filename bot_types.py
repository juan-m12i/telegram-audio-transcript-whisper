from typing import Callable, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

Condition = Callable[[str], bool]
ReplyAction = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine]
