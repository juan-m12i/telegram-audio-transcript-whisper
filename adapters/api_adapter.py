import os
import logging
import asyncio
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
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize the API adapter.
        
        Args:
            api_url: Base URL for the API (e.g., 'https://api.example.com')
            api_token: Bearer token for authentication
            timeout: Request timeout in seconds (default: 30.0)
            max_retries: Maximum number of retry attempts for transient errors (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 1.0, uses exponential backoff)
        """
        self.api_url = api_url or os.getenv("NOTES_API_URL")
        self.api_token = api_token or os.getenv("NOTES_API_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
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
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable (transient).
        
        Retryable errors include:
        - ReadTimeout, ConnectTimeout, WriteTimeout
        - Connection errors
        - 500, 502, 503, 504 HTTP status codes
        """
        if isinstance(error, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout)):
            return True
        if isinstance(error, httpx.RequestError):
            # Connection errors are usually retryable
            return True
        if isinstance(error, httpx.HTTPStatusError):
            # Retry on server errors (5xx) but not client errors (4xx)
            status_code = error.response.status_code
            return status_code >= 500 and status_code < 600
        return False

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
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    # Validate response structure
                    if "status" not in result or "note_id" not in result:
                        raise ValueError(f"Invalid API response format: {result}")
                    
                    if attempt > 0:
                        logging.info(f"API request succeeded on retry attempt {attempt + 1}")
                    
                    return {
                        "status": result["status"],  # 'created' or 'updated'
                        "note_id": result["note_id"],
                        "message_id": formatted_message_id
                    }
            
            except httpx.HTTPStatusError as e:
                last_error = e
                # Don't retry on client errors (4xx), only server errors (5xx)
                if e.response.status_code < 500:
                    logging.error(f"API request failed with status {e.response.status_code}: {e.response.text}")
                    raise Exception(f"API request failed: {e.response.status_code}")
                # Server error - might be retryable
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(
                        f"API request failed with status {e.response.status_code} (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logging.error(f"API request failed with status {e.response.status_code}: {e.response.text}")
                raise Exception(f"API request failed: {e.response.status_code}")
            
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(
                        f"API request timeout (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                error_type = type(e).__name__
                logging.error(f"API request timeout after {self.max_retries} attempts: {error_type}")
                raise Exception(f"API request timeout: {error_type}")
            
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(
                        f"API request error (attempt {attempt + 1}/{self.max_retries}): {type(e).__name__}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                error_type = type(e).__name__
                error_msg = str(e) if str(e) else error_type
                logging.error(f"API request error after {self.max_retries} attempts: {error_msg}")
                raise Exception(f"API request error: {error_msg}")
            
            except Exception as e:
                # Non-retryable errors (like ValueError) should not be retried
                logging.error(f"Unexpected error saving note to API: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_error:
            error_type = type(last_error).__name__
            error_msg = str(last_error) if str(last_error) else error_type
            raise Exception(f"API request failed after {self.max_retries} attempts: {error_msg}")

    async def save_food_log(
        self,
        message_id: str,
        text: str,
        chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Save or update a food log via HTTP API.
        
        The API handles idempotency - if the message_id already exists, it updates;
        otherwise, it creates a new food log entry.
        
        Args:
            message_id: Telegram message ID
            text: Food log text content
            chat_id: Optional chat ID for composite message ID
            
        Returns:
            Dict with status ('created' or 'updated'), log_id, and message_id
        """
        formatted_message_id = self._format_message_id(message_id, chat_id)
        
        payload = {
            "message_id": formatted_message_id,
            "text": text
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        endpoint = f"{self.api_url}/food-logs"
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    # Validate response structure
                    if "status" not in result or "log_id" not in result:
                        raise ValueError(f"Invalid API response format: {result}")
                    
                    if attempt > 0:
                        logging.info(f"Food log API request succeeded on retry attempt {attempt + 1}")
                    
                    return {
                        "status": result["status"],  # 'created' or 'updated'
                        "log_id": result["log_id"],
                        "message_id": formatted_message_id
                    }
            
            except httpx.HTTPStatusError as e:
                last_error = e
                # Don't retry on client errors (4xx), only server errors (5xx)
                if e.response.status_code < 500:
                    logging.error(f"Food log API request failed with status {e.response.status_code}: {e.response.text}")
                    raise Exception(f"Food log API request failed: {e.response.status_code}")
                # Server error - might be retryable
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(
                        f"Food log API request failed with status {e.response.status_code} (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logging.error(f"Food log API request failed with status {e.response.status_code}: {e.response.text}")
                raise Exception(f"Food log API request failed: {e.response.status_code}")
            
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(
                        f"Food log API request timeout (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                error_type = type(e).__name__
                logging.error(f"Food log API request timeout after {self.max_retries} attempts: {error_type}")
                raise Exception(f"Food log API request timeout: {error_type}")
            
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(
                        f"Food log API request error (attempt {attempt + 1}/{self.max_retries}): {type(e).__name__}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                error_type = type(e).__name__
                error_msg = str(e) if str(e) else error_type
                logging.error(f"Food log API request error after {self.max_retries} attempts: {error_msg}")
                raise Exception(f"Food log API request error: {error_msg}")
            
            except Exception as e:
                # Non-retryable errors (like ValueError) should not be retried
                logging.error(f"Unexpected error saving food log to API: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_error:
            error_type = type(last_error).__name__
            error_msg = str(last_error) if str(last_error) else error_type
            raise Exception(f"Food log API request failed after {self.max_retries} attempts: {error_msg}")
