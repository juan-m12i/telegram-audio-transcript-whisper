import asyncio
import os
import sys

os.environ.setdefault('ALLOWED_CHAT_IDS', '1')
os.environ.setdefault('STARTUP_CHAT_IDS_REPORT', '1')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot.bot_common import reply_builder
from bot.bot_conditions import condition_catch_all


async def dummy_action(update, context):
    dummy_action.called = True


def always_true(text):
    return True


def test_reply_builder(monkeypatch):
    dummy_action.called = False
    monkeypatch.setattr('bot.bot_common.allowed_user', lambda update: True)
    reply = reply_builder({always_true: dummy_action, condition_catch_all: dummy_action})

    class DummyMessage:
        def __init__(self):
            self.text = "hi"
        async def reply_text(self, text):
            pass
    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage()
            self.effective_chat = type('chat', (), {'id': 1})
    class DummyContext:
        pass

    asyncio.run(reply(DummyUpdate(), DummyContext()))
    assert dummy_action.called
