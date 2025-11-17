import os
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv
from notion_client import Client
from adapters.storage_adapter import StorageAdapter

load_dotenv()


class NotionAdapter(StorageAdapter):
    def __init__(self, auth_token: str = os.getenv("NOTION_TOKEN"), database_id: Optional[str] = None, 
                 parent_id: Optional[str] = None):
        self._client = Client(auth=auth_token)
        self._parent_id = parent_id or os.getenv("NOTION_PAGE_ID")
        # self._db = database_id or self._client.databases.retrieve(database_id)

    from datetime import datetime
    
    async def save_note(
        self,
        message_id: str,
        text: str,
        date_created: datetime,
        last_updated: datetime,
        chat_id: Optional[int] = None
    ) -> Dict[str, any]:
        """Save a note to Notion.
        
        Note: Notion doesn't support updating blocks by message_id, so this always creates
        a new block. For update tracking, use the API adapter instead.
        """
        # Use date_created for the block timestamp
        block_id = self.add_block(
            parent_id=self._parent_id,
            text=text,
            date=date_created,
            block_type="bulleted_list_item",
            prepend_timestamp=True
        )
        
        # Extract block ID from response
        note_id = block_id.get("id", message_id) if isinstance(block_id, dict) else str(block_id)
        
        return {
            "status": "created",
            "note_id": note_id,
            "message_id": message_id
        }

    def add_block(self, parent_id: str, text: str, date: datetime = None, attachment_url: str = None,
                  block_type: str = "paragraph", prepend_timestamp: bool = True):
        if block_type not in ["paragraph", "bulleted_list_item"]:
            raise ValueError("Invalid block_type. Must be 'paragraph' or 'bulleted_list_item'.")

        # Format timestamp and prepend to text content if requested
        if prepend_timestamp:
            if date is None:
                date = datetime.now()
            timestamp_str = date.strftime('%Y-%m-%d %H:%M:%S')
            formatted_text = f"[{timestamp_str}] {text}"
        else:
            formatted_text = text

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
                            "content": formatted_text
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
                            "content": formatted_text
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
