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

    from datetime import datetime

    def add_block(self, parent_id: str, text: str, date: datetime = None, attachment_url: str = None,
                  block_type: str = "paragraph"):
        if date is None:
            date = datetime.now()

        if block_type not in ["paragraph", "bulleted_list_item"]:
            raise ValueError("Invalid block_type. Must be 'paragraph' or 'bulleted_list_item'.")

        block_dict = {
            "object": "block",
            "type": block_type,
        }

        if block_type == "paragraph":
            block_dict["paragraph"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ]
            }
        elif block_type == "bulleted_list_item":
            block_dict["bulleted_list_item"] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ],
                "color": "default",
                "children": []
            }

        if attachment_url:
            attachment_block = {
                "object": "block",
                "type": "embed",
                "embed": {
                    "url": attachment_url
                }
            }
            block_dict[block_type]['rich_text'].append(attachment_block)

        ret = self._client.blocks.children.append(parent_id, children=[block_dict])

        return ret
