"""Queue worker for processing conversation requests.

Handles the worker loop that processes queued conversation requests
using the DMAssistant with database persistence.
"""

import asyncio
import logging
from typing import Optional

try:
    import discord
except ImportError:
    # Fallback for testing without discord.py
    discord = None

from src.ai.agents.conversation_queue import get_conversation_queue, ConversationRequest
from src.ai.agents.dm_assistant import DMAssistant
from src.ai.agents.langchain_dm_assistant import LangChainDMAssistant
from src.bot.voice_handler import get_voice_manager
from src.db.conversation_db import get_conversation_db

try:
    from src.config.settings import settings
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from src.config.settings import settings


logger = logging.getLogger(__name__)


class ConversationQueueWorker:
    """Worker that processes conversation requests from the queue."""
    
    def __init__(self, dm_assistant=None, use_langchain: bool = True, bot=None):
        """Initialize queue worker.

        Args:
            dm_assistant: DMAssistant instance to use for processing (legacy)
            use_langchain: Whether to use LangChain agent (default: True)
            bot: Discord bot instance (optional, required for voice features)
        """
        self.use_langchain = use_langchain
        self.bot = bot  # Store bot reference for voice channel operations

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
        """Stop the worker loop and ensure clean shutdown."""
        if not self.running:
            logger.info("Queue worker already stopped")
            return
        
        logger.info("Stopping queue worker...")
        self.running = False
        
        if self._worker_task:
            logger.info("Cancelling worker task...")
            self._worker_task.cancel()
            
            try:
                # Wait for the task to actually finish with a timeout
                await asyncio.wait_for(self._worker_task, timeout=5.0)
                logger.info("Worker task cancelled successfully")
            except asyncio.CancelledError:
                logger.info("Worker task cancelled")
            except asyncio.TimeoutError:
                logger.warning("Worker task did not stop within timeout")
            except Exception as e:
                logger.error(f"Error stopping worker task: {e}")
            finally:
                self._worker_task = None
        
        # Clear the DM assistant reference to break any potential reference cycles
        if hasattr(self, 'dm_assistant'):
            self.dm_assistant = None
            logger.info("DMAssistant reference cleared from queue worker")
        
        logger.info("Queue worker stopped completely")

    async def _process_voice_request(self, request: ConversationRequest) -> bool:
        """Process a voice channel request.

        Args:
            request: Voice request to process

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            # Check if bot reference is available
            if not self.bot:
                logger.error("Bot reference not available for voice request")
                if request.discord_channel:
                    await request.discord_channel.send(
                        "Voice features are not properly configured."
                    )
                return False

            voice_manager = get_voice_manager(self.bot)
            db = get_conversation_db()

            # Get the guild from the request
            user_id_int = int(request.user_id)
            guild_id_int = int(request.server_id)
            guild = self.bot.get_guild(guild_id_int)

            if not guild:
                logger.error(f"Guild {request.server_id} not found")
                if request.discord_channel:
                    await request.discord_channel.send(
                        "Selected server not found. Please try again."
                    )
                return False

            user = guild.get_member(user_id_int)
            if not user:
                logger.error(
                    f"User {request.user_id} not found in guild {guild.id}"
                )
                if request.discord_channel:
                    await request.discord_channel.send(
                        "You are not a member of the selected server."
                    )
                return False

            # Create private voice channel
            channel = await voice_manager.create_private_channel(guild, user)

            # Store session in database BEFORE joining (so cleanup can find it)
            session_id = db.create_voice_session(
                user_id=request.user_id,
                guild_id=str(guild.id),
                channel_id=str(channel.id)
            )

            if not session_id:
                logger.error("Failed to create voice session in database")
                await channel.delete(reason="Database error")
                return False

            # Join channel (this may fail if PyNaCl is missing)
            try:
                # Check if STT is enabled to determine which voice client to use
                if settings.ENABLE_STT:
                    # Use VoiceRecvClient for STT support
                    try:
                        from discord.ext import voice_recv
                        voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
                        logger.info(f"Connected to voice channel {channel.id} with VoiceRecvClient for STT")
                    except ImportError as import_error:
                        logger.warning(f"discord-ext-voice-recv not available: {import_error}")
                        logger.info("Falling back to standard voice client (STT disabled for this session)")
                        voice_client = await voice_manager.join_channel(channel)
                else:
                    # Use standard voice client
                    voice_client = await voice_manager.join_channel(channel)

                # If STT is enabled and VoiceRecvClient is available, start listening
                if settings.ENABLE_STT and hasattr(voice_client, 'listen'):
                    try:
                        from src.bot.audio_sink import STTAudioSink

                        # Create audio sink with session_id and channel_id
                        audio_sink = STTAudioSink(
                            session_id=session_id,
                            channel_id=channel.id
                        )

                        # Start listening to voice channel
                        voice_client.listen(audio_sink)

                        # Store audio_sink reference in voice_client for cleanup
                        voice_client._stt_audio_sink = audio_sink

                        # Start processing thread for the user
                        # Note: Processing threads are created dynamically when users join
                        # and start speaking (handled in AudioSink.write() method)

                        logger.info(f"Started STT listening for session {session_id} in channel {channel.id}")

                    except ImportError as import_error:
                        logger.warning(f"STT audio sink not available: {import_error}")
                    except Exception as stt_error:
                        logger.error(f"Failed to start STT listening: {stt_error}", exc_info=True)
                        # Continue without STT rather than failing completely

            except Exception as e:
                logger.error(f"Failed to join voice channel: {e}")
                # Cleanup: delete channel and end session
                await channel.delete(reason="Failed to join voice channel")
                db.end_voice_session(session_id)
                if request.discord_channel:
                    await request.discord_channel.send(
                        f"Failed to join voice channel: {e}\n"
                        "PyNaCl library may be missing. Ask admin to run: pip install PyNaCl"
                    )
                return False

            # Start alone timer
            await voice_manager.start_alone_timer(
                channel_id=channel.id,
                user_id=request.user_id,
                session_id=session_id
            )

            # Send success message
            if request.discord_channel:
                await request.discord_channel.send(
                    f"Voice channel created: {channel.mention}\n"
                    f"Join within {settings.VOICE_TIMEOUT} seconds."
                )

            logger.info(
                f"Voice session created for user {request.user_id} "
                f"in guild {guild.name} (session_id: {session_id})"
            )
            return True

        except discord.HTTPException as e:
            logger.error(f"Discord error processing voice request: {e}")
            if request.discord_channel:
                await request.discord_channel.send(
                    f"Failed to create voice channel: {e}"
                )
            return False
        except Exception as e:
            logger.error(f"Unexpected error processing voice request: {e}")
            if request.discord_channel:
                await request.discord_channel.send(
                    "An error occurred while creating the voice channel."
                )
            return False

    async def _log_conversation_message(
        self, 
        user_id: str, 
        server_id: str, 
        role: str, 
        content: str
    ) -> None:
        """Log a conversation message to the database.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server ID (or "0" for DMs)
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        try:
            from src.db.conversation_db import get_conversation_db
            
            # Get conversation database instance
            conv_db = get_conversation_db()
            
            # For DM contexts (when server_id might be None), use "0" as the server ID
            effective_server_id = server_id if server_id else "0"
            
            # Add message to conversation history
            success = conv_db.add_message(
                user_id=user_id,
                server_id=effective_server_id,
                role=role,
                content=content
            )
            
            if success:
                logger.debug(f"Logged {role} message for user {user_id} in server {effective_server_id}")
            else:
                logger.warning(f"Failed to log {role} message for user {user_id} in server {effective_server_id}")
                
        except (ImportError, AttributeError, ConnectionError, RuntimeError) as e:
            logger.error(f"Error logging conversation message: {e}")
            # Don't raise the exception - conversation logging failure shouldn't stop message processing
    
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
            except (RuntimeError, ValueError, TypeError, AttributeError, ConnectionError) as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(5.0)  # Brief pause before retrying
    
    async def _process_request(self, request: ConversationRequest) -> bool:
        """Process a single conversation request.
        
        Args:
            request: Request to process
            
        Returns:
            True if processed successfully, False otherwise
        """
        user_message_logged = False
        
        try:
            logger.info(f"Processing request for user {request.user_id}")
            
            # Add timeout handling
            timeout_seconds = 60  # 1 minute timeout

            # Route based on request type
            if request.request_type == "voice":
                logger.info(f"Processing voice request from user {request.user_id}")
                return await self._process_voice_request(request)

            # Process as stateless chat completion - no conversation history
            logger.info(f"Processing stateless request from user {request.user_id}")

            # Log user message to database before processing
            await self._log_conversation_message(
                user_id=request.user_id,
                server_id=request.server_id,
                role="user",
                content=request.message
            )
            user_message_logged = True
            
            # Generate stateless response using DMAssistant
            if self.use_langchain:
                # LangChain assistant - stateless completion
                response = await asyncio.wait_for(
                    self.dm_assistant.respond_to_dm(
                        message=request.message,
                        user_id=request.user_id,
                        user_name=f"User_{request.user_id}",
                        server_id=request.server_id
                    ),
                    timeout=timeout_seconds
                )
            else:
                # Legacy assistant - stateless completion
                response = await asyncio.wait_for(
                    self.dm_assistant.respond_to_dm(
                        message=request.message,
                        user_id=request.user_id,
                        user_name=f"User_{request.user_id}",
                        server_id=request.server_id
                    ),
                    timeout=timeout_seconds
                )
            
            # Log LLM response to database after processing
            await self._log_conversation_message(
                user_id=request.user_id,
                server_id=request.server_id,
                role="assistant",
                content=response
            )
            
            # Send response back to Discord
            if request.discord_channel:
                try:
                    await request.discord_channel.send(response)
                    logger.info(f"Response sent to user {request.user_id}")
                except (discord.HTTPException, discord.Forbidden, ConnectionError, AttributeError) if discord else (AttributeError, ConnectionError) as e:
                    logger.error(f"Error sending response to Discord for user {request.user_id}: {e}")
                    return False
            else:
                logger.info(f"Generated response for user {request.user_id}: {response[:50]}...")
            
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Request timed out for user {request.user_id} after {timeout_seconds} seconds")
            
            # Log the user message if not already logged
            if not user_message_logged:
                await self._log_conversation_message(
                    user_id=request.user_id,
                    server_id=request.server_id,
                    role="user",
                    content=request.message
                )
            
            # Log the timeout as an assistant response
            timeout_response = "⏰ **Request Timeout**: Your request took too long to process. Please try again with a simpler question."
            await self._log_conversation_message(
                user_id=request.user_id,
                server_id=request.server_id,
                role="assistant",
                content=timeout_response
            )
            
            # Notify user of timeout
            if request.discord_channel:
                try:
                    await request.discord_channel.send(timeout_response)
                except (discord.HTTPException, discord.Forbidden, ConnectionError, AttributeError) if discord else (AttributeError, ConnectionError) as e:
                    logger.error(f"Error sending timeout notification to user {request.user_id}: {e}")
            
            return False
        except (RuntimeError, ValueError, TypeError, AttributeError, ConnectionError, ImportError) as e:
            logger.error(f"Error processing request for user {request.user_id}: {e}")
            
            # Log the user message if not already logged
            if not user_message_logged:
                await self._log_conversation_message(
                    user_id=request.user_id,
                    server_id=request.server_id,
                    role="user",
                    content=request.message
                )
            
            # Log the error as an assistant response
            error_response = "❌ **Processing Error**: Something went wrong while processing your request. Please try again later."
            await self._log_conversation_message(
                user_id=request.user_id,
                server_id=request.server_id,
                role="assistant",
                content=error_response
            )
            
            # Notify user of error
            if request.discord_channel:
                try:
                    await request.discord_channel.send(error_response)
                except (discord.HTTPException, discord.Forbidden, ConnectionError, AttributeError) if discord else (AttributeError, ConnectionError) as e:
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


def initialize_queue_worker(dm_assistant=None, use_langchain: bool = True, bot=None) -> ConversationQueueWorker:
    """Initialize the global queue worker.

    Args:
        dm_assistant: DMAssistant instance to use (legacy, optional)
        use_langchain: Whether to use LangChain agent (default: True)
        bot: Discord bot instance (optional, required for voice features)

    Returns:
        ConversationQueueWorker instance
    """
    global _queue_worker

    if _queue_worker is None:
        _queue_worker = ConversationQueueWorker(dm_assistant, use_langchain, bot)
        logger.info(f"Queue worker initialized with {'LangChain' if use_langchain else 'legacy'} agent")

    return _queue_worker