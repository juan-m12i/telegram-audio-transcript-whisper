import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from notion_client import Client
load_dotenv()





class NotionAdapter:
    def __init__(self, auth_token: str = os.getenv("NOTION_TOKEN"), database_id: Optional[str] = None):
        self._client = Client(auth=auth_token)
        # self._db = database_id or self._client.databases.retrieve(database_id)

    def add_block(self, parent_id: str, text: str, date: datetime = None, attachment_url: str = None):
        parent_block = self._client.pages.retrieve(parent_id)

        block_dict = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Hello world"
                        }
                    }
                ]
            }
        }

        ret = self._client.blocks.children.append(parent_id, children=[block_dict])

        return ret
