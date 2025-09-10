"""Queue system for managing DMAssistant conversation requests.

Provides thread-safe queuing of conversation requests with anti-spam protection
and conversation history loading from database.
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

try:
    from ..db.conversation_db import get_conversation_db
except ImportError:
    # Fallback for testing
    from src.db.conversation_db import get_conversation_db


logger = logging.getLogger(__name__)


class RequestStatus(Enum):
    """Status of a conversation request."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConversationRequest:
    """A conversation request in the queue."""
    
    user_id: str
    server_id: str
    message: str
    timestamp: datetime
    discord_message_id: Optional[int] = None
    discord_channel: Optional[object] = None  # Discord channel for message updates
    status: RequestStatus = RequestStatus.QUEUED
    status_message_id: Optional[int] = None  # ID of status message to edit


class ConversationQueue:
    """Thread-safe queue for managing DMAssistant requests."""
    
    def __init__(self, max_queue_size: int = 50, request_timeout: int = 300):
        """Initialize conversation queue.
        
        Args:
            max_queue_size: Maximum number of queued requests
            request_timeout: Timeout in seconds for individual requests
        """
        self.max_queue_size = max_queue_size
        self.request_timeout = request_timeout
        
        # Thread-safe queue and tracking
        self._queue: asyncio.Queue[ConversationRequest] = asyncio.Queue(maxsize=max_queue_size)
        self._active_requests: Dict[str, ConversationRequest] = {}  # user_id -> request
        self._queue_order: List[str] = []  # Track queue position order
        self._processing_lock = asyncio.Lock()
        
        # Statistics
        self._total_processed = 0
        self._total_failed = 0
        
        logger.info(f"ConversationQueue initialized (max_size={max_queue_size}, timeout={request_timeout}s)")
    
    def is_user_queued(self, user_id: str) -> bool:
        """Check if user already has a request queued or processing."""
        return user_id in self._active_requests
    
    async def add_request(self, user_id: str, server_id: str, message: str, discord_message_id: Optional[int] = None, discord_channel=None) -> bool:
        """Add a conversation request to the queue.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server ID
            message: User's message content
            discord_message_id: Optional Discord message ID for status updates
            discord_channel: Optional Discord channel for status updates
            
        Returns:
            True if request added successfully, False if rejected
        """
        # Anti-spam protection: Check if user already has active request
        if self.is_user_queued(user_id):
            logger.warning(f"User {user_id} already has active request, rejecting new request")
            return False
        
        # Check if queue is full
        if self._queue.full():
            logger.warning(f"Queue is full ({self.max_queue_size}), rejecting request from user {user_id}")
            return False
        
        # Create and queue request
        request = ConversationRequest(
            user_id=user_id,
            server_id=server_id,
            message=message,
            timestamp=datetime.now(),
            discord_message_id=discord_message_id,
            discord_channel=discord_channel
        )
        
        try:
            await self._queue.put(request)
            self._active_requests[user_id] = request
            self._queue_order.append(user_id)  # Track queue position
            
            logger.info(f"Added request to queue: user {user_id}, queue size: {self.get_queue_size()}")
            return True
            
        except asyncio.QueueFull:
            logger.error(f"Queue unexpectedly full when adding request for user {user_id}")
            return False
    
    async def get_next_request(self) -> Optional[ConversationRequest]:
        """Get the next request from queue for processing.
        
        Returns:
            Next request to process, or None if queue is empty
        """
        try:
            request = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            request.status = RequestStatus.PROCESSING
            
            # Remove from queue order tracking
            if request.user_id in self._queue_order:
                self._queue_order.remove(request.user_id)
            
            logger.info(f"Processing request for user {request.user_id}")
            return request
            
        except asyncio.TimeoutError:
            return None
    
    async def complete_request(self, request: ConversationRequest, success: bool = True) -> None:
        """Mark request as completed and remove from active tracking.
        
        Args:
            request: The completed request
            success: Whether request completed successfully
        """
        async with self._processing_lock:
            # Remove from active requests
            if request.user_id in self._active_requests:
                del self._active_requests[request.user_id]
            
            # Update status and statistics
            request.status = RequestStatus.COMPLETED if success else RequestStatus.FAILED
            
            if success:
                self._total_processed += 1
            else:
                self._total_failed += 1
            
            logger.info(f"Request completed for user {request.user_id}, success: {success}")
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    def get_queue_position(self, user_id: str) -> Optional[int]:
        """Get user's position in queue (1-based).
        
        Args:
            user_id: User to check position for
            
        Returns:
            Position in queue (1 = next), None if not queued
        """
        if user_id not in self._active_requests:
            return None
        
        try:
            # Return 1-based position in queue
            return self._queue_order.index(user_id) + 1
        except ValueError:
            # User not in queue order (shouldn't happen)
            return None
    
    async def load_conversation_history(self, user_id: str, server_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """Load conversation history for request processing.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server ID
            limit: Maximum messages to load
            
        Returns:
            List of conversation messages for DMAssistant context
        """
        def _load_history():
            """Load history in thread pool to avoid blocking."""
            conv_db = get_conversation_db()
            history = conv_db.get_conversation_history(user_id, server_id, limit=limit)
            
            # Convert to DMAssistant format
            messages = []
            for msg in history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            return messages
        
        try:
            # Run database operation in thread pool for better concurrency
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(None, _load_history)
            
            logger.debug(f"Loaded {len(messages)} messages for user {user_id} in server {server_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Error loading conversation history for user {user_id}: {e}")
            return []
    
    async def store_conversation_messages(self, user_id: str, server_id: str, user_message: str, assistant_response: str) -> None:
        """Store conversation messages to database.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server ID
            user_message: User's message content
            assistant_response: Assistant's response content
        """
        def _store_messages():
            """Store messages in thread pool to avoid blocking."""
            conv_db = get_conversation_db()
            
            # Store user message
            conv_db.add_message(user_id, server_id, "user", user_message)
            
            # Store assistant response
            conv_db.add_message(user_id, server_id, "assistant", assistant_response)
        
        try:
            # Run database operation in thread pool for better concurrency
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _store_messages)
            
            logger.debug(f"Stored conversation messages for user {user_id} in server {server_id}")
            
        except Exception as e:
            logger.error(f"Error storing conversation messages for user {user_id}: {e}")
    
    async def update_request_status(self, request: ConversationRequest, status_text: str) -> None:
        """Update the status message for a request.
        
        Args:
            request: Request to update status for
            status_text: New status text to display
        """
        if not request.discord_channel or not hasattr(request.discord_channel, 'send'):
            return
        
        try:
            if request.status_message_id:
                # Edit existing status message
                try:
                    status_message = await request.discord_channel.fetch_message(request.status_message_id)
                    await status_message.edit(content=status_text)
                except:
                    # If editing fails, send new message
                    new_message = await request.discord_channel.send(status_text)
                    request.status_message_id = new_message.id
            else:
                # Send new status message
                new_message = await request.discord_channel.send(status_text)
                request.status_message_id = new_message.id
                
        except Exception as e:
            logger.error(f"Error updating status for user {request.user_id}: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        return {
            "queue_size": self.get_queue_size(),
            "active_requests": len(self._active_requests),
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "max_queue_size": self.max_queue_size
        }


# Global queue instance
_conversation_queue: Optional[ConversationQueue] = None


def get_conversation_queue() -> ConversationQueue:
    """Get the global conversation queue instance.
    
    Returns:
        ConversationQueue instance
    """
    global _conversation_queue
    
    if _conversation_queue is None:
        _conversation_queue = ConversationQueue()
    
    return _conversation_queue


def initialize_conversation_queue(max_queue_size: int = 50, request_timeout: int = 300) -> None:
    """Initialize the conversation queue explicitly.
    
    Args:
        max_queue_size: Maximum number of queued requests
        request_timeout: Timeout in seconds for individual requests
    """
    global _conversation_queue
    
    if _conversation_queue is None:
        _conversation_queue = ConversationQueue(max_queue_size, request_timeout)
        logger.info("Conversation queue initialized during startup")