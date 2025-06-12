import asyncio
import os
import sys
from types import SimpleNamespace
import httpx
import pytest

os.environ.setdefault('OPEN_AI_API_KEY', 'test')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from adapters.whisper_adapter import transcribe_audio_file


class MockResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data or {}

    def json(self):
        return self._json


class MockClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def post(self, *args, **kwargs):
        return MockResponse(200, '{"text": "Hello world. Bye."}', {"text": "Hello world. Bye."})


def test_transcribe_audio_file(tmp_path, monkeypatch):
    audio_file = tmp_path / "test.m4a"
    audio_file.write_bytes(b"dummy")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())

    result = asyncio.run(transcribe_audio_file(str(audio_file)))
    assert result == ["Hello world.Bye."]
