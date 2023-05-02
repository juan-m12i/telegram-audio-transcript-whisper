import os
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
load_dotenv()

class NotionAdapter:
    def __init__(self, database_id: str, auth_token: str = os.getenv("NOTION_TOKEN")):
        self._client = Client(auth=auth_token)
        self._db = self._client.databases.retrieve(database_id)

    def add_block(self, text: str, date: datetime = None, attachment_url: str = None):
        new_page = self._db.collection.add()
        new_page.title = text

        if date:
            new_page.date = date

        if attachment_url:
            new_page.attachments = [{
                "type": "file",
                "name": attachment_url.split("/")[-1],
                "file": {"url": attachment_url}
            }]
