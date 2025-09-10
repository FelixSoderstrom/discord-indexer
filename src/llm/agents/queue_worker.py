"""Queue worker for processing conversation requests.

Handles the worker loop that processes queued conversation requests
using the DMAssistant with database persistence.
"""

import asyncio
import logging
from typing import Optional

from .conversation_queue import get_conversation_queue, ConversationRequest
from .dm_assistant import DMAssistant
from .langchain_dm_assistant import LangChainDMAssistant


logger = logging.getLogger(__name__)


class ConversationQueueWorker:
    """Worker that processes conversation requests from the queue."""
    
    def __init__(self, dm_assistant=None, use_langchain: bool = True):
        """Initialize queue worker.
        
        Args:
            dm_assistant: DMAssistant instance to use for processing (legacy)
            use_langchain: Whether to use LangChain agent (default: True)
        """
        self.use_langchain = use_langchain
        
        if use_langchain:
            self.dm_assistant = LangChainDMAssistant()
            logger.info("ConversationQueueWorker initialized with LangChain agent")
        else:
            self.dm_assistant = dm_assistant or DMAssistant()
            logger.info("ConversationQueueWorker initialized with legacy DMAssistant")
        
        self.queue = get_conversation_queue()
        self.running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the worker loop."""
        if self.running:
            logger.warning("Worker already running")
            return
        
        self.running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Queue worker started")
    
    async def stop(self) -> None:
        """Stop the worker loop."""
        if not self.running:
            return
        
        self.running = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Queue worker stopped")
    
    async def _worker_loop(self) -> None:
        """Main worker loop that processes requests."""
        logger.info("Queue worker loop started")
        
        while self.running:
            try:
                # Get next request from queue
                request = await self.queue.get_next_request()
                
                if request is None:
                    # No requests available, continue polling
                    await asyncio.sleep(1.0)
                    continue
                
                # Update status to processing
                await self.queue.update_request_status(request, "🤖 **Processing your request...**")
                
                # Process the request
                success = await self._process_request(request)
                
                # Mark request as completed
                await self.queue.complete_request(request, success)
                
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(5.0)  # Brief pause before retrying
    
    async def _process_request(self, request: ConversationRequest) -> bool:
        """Process a single conversation request.
        
        Args:
            request: Request to process
            
        Returns:
            True if processed successfully, False otherwise
        """
        try:
            logger.info(f"Processing request for user {request.user_id}")
            
            # Add timeout handling
            timeout_seconds = 60  # 1 minute timeout
            
            # Load conversation history
            history = await asyncio.wait_for(
                self.queue.load_conversation_history(
                    request.user_id, 
                    request.server_id,
                    limit=20
                ),
                timeout=timeout_seconds
            )
            
            # Add conversation history to DMAssistant (if any)
            if history:
                # DMAssistant will handle the conversation context
                # For now, we use the existing respond_to_dm method
                pass
            
            # Generate response using DMAssistant with timeout
            response = await asyncio.wait_for(
                self.dm_assistant.respond_to_dm(
                    message=request.message,
                    user_id=request.user_id,
                    user_name=f"User_{request.user_id}",
                    server_id=request.server_id
                ),
                timeout=timeout_seconds
            )
            
            # Store conversation in database
            await self.queue.store_conversation_messages(
                request.user_id,
                request.server_id,
                request.message,
                response
            )
            
            # Send response back to Discord
            if request.discord_channel:
                try:
                    await request.discord_channel.send(response)
                    logger.info(f"Response sent to user {request.user_id}")
                except Exception as e:
                    logger.error(f"Error sending response to Discord for user {request.user_id}: {e}")
                    return False
            else:
                logger.info(f"Generated response for user {request.user_id}: {response[:50]}...")
            
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Request timed out for user {request.user_id} after {timeout_seconds} seconds")
            
            # Notify user of timeout
            if request.discord_channel:
                try:
                    await request.discord_channel.send(
                        "⏰ **Request Timeout**: Your request took too long to process. "
                        "Please try again with a simpler question."
                    )
                except Exception as e:
                    logger.error(f"Error sending timeout notification to user {request.user_id}: {e}")
            
            return False
        except Exception as e:
            logger.error(f"Error processing request for user {request.user_id}: {e}")
            
            # Notify user of error
            if request.discord_channel:
                try:
                    await request.discord_channel.send(
                        "❌ **Processing Error**: Something went wrong while processing your request. "
                        "Please try again later."
                    )
                except Exception as e:
                    logger.error(f"Error sending error notification to user {request.user_id}: {e}")
            
            return False


# Global worker instance
_queue_worker: Optional[ConversationQueueWorker] = None


def get_queue_worker() -> Optional[ConversationQueueWorker]:
    """Get the global queue worker instance.
    
    Returns:
        ConversationQueueWorker instance or None if not initialized
    """
    return _queue_worker


def initialize_queue_worker(dm_assistant=None, use_langchain: bool = True) -> ConversationQueueWorker:
    """Initialize the global queue worker.
    
    Args:
        dm_assistant: DMAssistant instance to use (legacy, optional)
        use_langchain: Whether to use LangChain agent (default: True)
        
    Returns:
        ConversationQueueWorker instance
    """
    global _queue_worker
    
    if _queue_worker is None:
        _queue_worker = ConversationQueueWorker(dm_assistant, use_langchain)
        logger.info(f"Queue worker initialized with {'LangChain' if use_langchain else 'legacy'} agent")
    
    return _queue_worker