import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import httpx
from adapters.storage_adapter import StorageAdapter

load_dotenv()


class ApiAdapter(StorageAdapter):
    """Adapter for storing notes via HTTP API.
    
    The API handles idempotency - if a message_id is sent that already exists,
    it updates the existing note. Otherwise, it creates a new one.
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout: float = 10.0
    ):
        """Initialize the API adapter.
        
        Args:
            api_url: Base URL for the API (e.g., 'https://api.example.com')
            api_token: Bearer token for authentication
            timeout: Request timeout in seconds
        """
        self.api_url = api_url or os.getenv("NOTES_API_URL")
        self.api_token = api_token or os.getenv("NOTES_API_TOKEN")
        self.timeout = timeout
        
        if not self.api_url:
            raise ValueError("NOTES_API_URL environment variable is required")
        if not self.api_token:
            raise ValueError("NOTES_API_TOKEN environment variable is required")
        
        # Ensure API URL doesn't end with a slash
        self.api_url = self.api_url.rstrip('/')
    
    def _format_message_id(self, message_id: str, chat_id: Optional[int] = None) -> str:
        """Format message_id for API.
        
        Creates a composite identifier using chat_id and message_id if chat_id is provided.
        """
        if chat_id is not None:
            return f"{chat_id}_{message_id}"
        return message_id
    
    async def save_note(
        self,
        message_id: str,
        text: str,
        date_created: datetime,
        last_updated: datetime,
        chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Save or update a note via HTTP API.
        
        The API handles idempotency - if the message_id already exists, it updates;
        otherwise, it creates a new note.
        
        Note: date_created and last_updated are managed by the server, so they are
        not sent in the request (but kept in signature for interface compatibility).
        """
        formatted_message_id = self._format_message_id(message_id, chat_id)
        
        # Server manages date_created and last_updated, so we don't send them
        payload = {
            "message_id": formatted_message_id,
            "text": text
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        endpoint = f"{self.api_url}/notes"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                # Validate response structure
                if "status" not in result or "note_id" not in result:
                    raise ValueError(f"Invalid API response format: {result}")
                
                return {
                    "status": result["status"],  # 'created' or 'updated'
                    "note_id": result["note_id"],
                    "message_id": formatted_message_id
                }
        
        except httpx.HTTPStatusError as e:
            logging.error(f"API request failed with status {e.response.status_code}: {e.response.text}")
            raise Exception(f"API request failed: {e.response.status_code}")
        except httpx.RequestError as e:
            logging.error(f"API request error: {e}")
            raise Exception(f"API request error: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error saving note to API: {e}")
            raise

