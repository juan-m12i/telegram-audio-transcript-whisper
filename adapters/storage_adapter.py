from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional


class StorageAdapter(ABC):
    """Abstract base class for storage adapters.
    
    This defines the interface that all storage backends (Notion, API, etc.)
    must implement. It allows different bots to use different storage backends
    while maintaining a consistent interface.
    """
    
    @abstractmethod
    async def save_note(
        self,
        message_id: str,
        text: str,
        date_created: datetime,
        last_updated: datetime,
        chat_id: Optional[int] = None
    ) -> Dict[str, any]:
        """Save or update a note.
        
        Args:
            message_id: Unique identifier for the message (e.g., Telegram message_id)
            text: The note content/text
            date_created: When the note was first created
            last_updated: When the note was last updated
            chat_id: Optional chat identifier (for composite message_id)
        
        Returns:
            Dictionary with at least:
            - 'status': 'created' or 'updated'
            - 'note_id': Unique identifier for the stored note
            - 'message_id': The message_id that was used
        
        Raises:
            Exception: If the save operation fails
        """
        pass

