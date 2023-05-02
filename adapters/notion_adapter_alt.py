import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from notion.client import NotionClient, Block
load_dotenv()

class NotionAdapter:
    def __init__(self, auth_token: str = os.getenv("NOTION_TOKEN"), database_id: Optional[str] = None):
        self._client = NotionClient(token_v2=auth_token)
        # self._db = database_id or self._client.databases.retrieve(database_id)

    def add_block(self, parent_id: str, text: str, date: datetime = None, attachment_url: str = None):
        # parent_block = self._client.pages.retrieve(parent_id)
        # page = client.get_block("https://www.notion.so/myorg/Test-c0d20a71c0944985ae96e661ccc99821")
        page = client.get_block("https://www.notion.so/Telegram-Notes-20fe25981f634cea8d90098dddb543a0")


        new_block = Block(parent=page, type="paragraph")
        new_block.title = [{"type": "text", "text": {"content": text}}]

        if date is None:
            new_block.created_time = date.isoformat()

        if attachment_url:
            new_block.children.add_new(type="embed", embed=attachment_url)

        return new_block.id
