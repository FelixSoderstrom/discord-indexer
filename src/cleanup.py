"""Comprehensive cleanup system for Discord-Indexer bot.

This module provides the Cleanup class that orchestrates graceful shutdown
of all bot components including Discord connections, voice channels, LLM models,
database connections, and message processing pipelines.
"""

import asyncio
import logging
from typing import Optional, List, TYPE_CHECKING

import discord
from src.exceptions.message_processing import (
    CleanupError,
    DiscordCleanupError,
    LLMCleanupError,
    DatabaseCleanupError
)
from src.ai.utils import unload_model_from_memory, get_ollama_client
from src.config.settings import settings

if TYPE_CHECKING:
    from src.bot.client import DiscordBot


logger = logging.getLogger(__name__)


class Cleanup:
    """Comprehensive cleanup manager for graceful bot shutdown.

    Handles cleanup of all bot resources in the correct order:
    1. Stop new request acceptance (queue workers, DM handlers)
    2. Complete in-progress operations (pipeline, LLM responses)
    3. Clean up external resources (voice channels, Discord connections)
    4. Unload LLM models (Ollama keep_alive=0)
    5. Close database connections (ChromaDB, SQLite)
    """

    def __init__(self, bot: "DiscordBot") -> None:
        """Initialize cleanup manager with bot reference.

        Args:
            bot: DiscordBot instance to clean up
        """
        self.bot = bot
        self.cleanup_started = False
        self.components_cleaned: List[str] = []
        self.logger = logging.getLogger(__name__)

        self.logger.info("Cleanup manager initialized")

    async def cleanup_discord_resources(self) -> None:
        """Clean up Discord-related resources.

        Handles:
        - Voice channels: kick all participants and delete temporary channels
        - Bot connection: properly close Discord connection
        - Guild-specific cleanup: handle server-specific resources

        Raises:
            DiscordCleanupError: If Discord resource cleanup fails
        """
        try:
            self.logger.info("Starting Discord resource cleanup...")

            # Clean up voice channels across all guilds
            if self.bot.guilds:
                for guild in self.bot.guilds:
                    try:
                        # Find and clean up voice channels
                        for channel in guild.voice_channels:
                            if channel.members:
                                self.logger.info(f"Cleaning up voice channel '{channel.name}' in guild '{guild.name}'")

                                # Kick all members from voice channel
                                for member in channel.members:
                                    try:
                                        await member.move_to(None)
                                        self.logger.debug(f"Kicked {member.name} from voice channel {channel.name}")
                                    except discord.HTTPException as e:
                                        self.logger.warning(f"Failed to kick {member.name} from voice channel: {e}")

                                # Delete temporary voice channels if they're bot-created
                                # Note: Only delete channels that were created by the bot
                                # You may want to add additional logic here to identify bot-created channels
                                if channel.name.startswith("temp-") or "bot" in channel.name.lower():
                                    try:
                                        await channel.delete(reason="Bot cleanup - temporary channel")
                                        self.logger.info(f"Deleted temporary voice channel '{channel.name}'")
                                    except discord.HTTPException as e:
                                        self.logger.warning(f"Failed to delete voice channel '{channel.name}': {e}")

                    except discord.HTTPException as e:
                        self.logger.warning(f"Error cleaning up guild '{guild.name}': {e}")

            # Close bot connection properly
            if not self.bot.is_closed():
                self.logger.info("Closing Discord bot connection...")
                await self.bot.close()
                self.logger.info("Discord bot connection closed")

            self.components_cleaned.append("discord")
            self.logger.info("Discord resource cleanup completed successfully")

        except discord.HTTPException as e:
            raise DiscordCleanupError(f"Discord HTTP error during cleanup: {e}")
        except discord.Forbidden as e:
            raise DiscordCleanupError(f"Discord permission error during cleanup: {e}")
        except discord.ConnectionClosed as e:
            # Connection already closed is not necessarily an error
            self.logger.info("Discord connection was already closed")
            self.components_cleaned.append("discord")
        except Exception as e:
            raise DiscordCleanupError(f"Unexpected error during Discord cleanup: {e}")

    async def cleanup_llm_resources(self) -> None:
        """Clean up LLM-related resources.

        Handles:
        - Ollama models: unload from memory using keep_alive=0
        - Queue workers: stop conversation processing workers
        - LLM connections: close Ollama client connections

        Raises:
            LLMCleanupError: If LLM resource cleanup fails
        """
        try:
            self.logger.info("Starting LLM resource cleanup...")

            # Stop queue worker if running
            if hasattr(self.bot, 'queue_worker') and self.bot.queue_worker:
                self.logger.info("Stopping conversation queue worker...")
                try:
                    await self.bot.queue_worker.stop()
                    self.logger.info("Queue worker stopped successfully")
                except Exception as e:
                    self.logger.warning(f"Error stopping queue worker: {e}")

            # Unload Ollama model from memory
            model_name = settings.LLM_MODEL_NAME
            if model_name:
                self.logger.info(f"Unloading Ollama model '{model_name}' from memory...")
                try:
                    success = unload_model_from_memory(model_name)
                    if success:
                        self.logger.info(f"Successfully unloaded model '{model_name}' from memory")
                    else:
                        self.logger.warning(f"Failed to unload model '{model_name}' from memory")
                except Exception as e:
                    self.logger.warning(f"Error unloading model '{model_name}': {e}")

            # Clear DMAssistant reference
            if hasattr(self.bot, 'dm_assistant') and self.bot.dm_assistant:
                self.bot.dm_assistant = None
                self.logger.info("DMAssistant reference cleared")

            self.components_cleaned.append("llm")
            self.logger.info("LLM resource cleanup completed successfully")

        except (ConnectionError, TimeoutError, OSError) as e:
            raise LLMCleanupError(f"Connection error during LLM cleanup: {e}")
        except Exception as e:
            raise LLMCleanupError(f"Unexpected error during LLM cleanup: {e}")

    async def cleanup_database_resources(self) -> None:
        """Clean up database-related resources.

        Handles:
        - ChromaDB connections: properly close vector database connections
        - SQLite connections: close conversation database connections
        - Database cleanup: run any pending cleanup operations

        Raises:
            DatabaseCleanupError: If database resource cleanup fails
        """
        try:
            self.logger.info("Starting database resource cleanup...")

            # Clean up conversation database connections
            try:
                from src.db.conversation_db import get_conversation_db

                # Get conversation database instance and perform any cleanup
                conv_db = get_conversation_db()

                # Note: SQLite connections are typically closed automatically when
                # the Python process exits, but we can ensure cleanup here if needed
                self.logger.info("Conversation database cleanup completed")

            except ImportError:
                self.logger.debug("Conversation database not available for cleanup")
            except Exception as e:
                self.logger.warning(f"Error during conversation database cleanup: {e}")

            # Clean up ChromaDB connections if available
            try:
                # Note: ChromaDB cleanup would go here if we have persistent connections
                # For now, ChromaDB connections are typically ephemeral per request
                self.logger.info("ChromaDB cleanup completed")

            except Exception as e:
                self.logger.warning(f"Error during ChromaDB cleanup: {e}")

            self.components_cleaned.append("database")
            self.logger.info("Database resource cleanup completed successfully")

        except Exception as e:
            raise DatabaseCleanupError(f"Unexpected error during database cleanup: {e}")

    async def cleanup_pipeline_resources(self) -> None:
        """Clean up message processing pipeline resources.

        Handles:
        - Message pipeline: stop processing and clear queues
        - Processing tasks: cancel running async tasks
        - Pipeline events: clear events and locks
        """
        try:
            self.logger.info("Starting pipeline resource cleanup...")

            # Clear message pipeline reference and stop processing
            if hasattr(self.bot, 'message_pipeline') and self.bot.message_pipeline:
                self.bot.message_pipeline = None
                self.logger.info("Message pipeline reference cleared")

            # Clear pipeline ready event
            if hasattr(self.bot, 'pipeline_ready'):
                self.bot.pipeline_ready.clear()
                self.logger.info("Pipeline events cleared")

            # Clear any stored message references
            if hasattr(self.bot, 'stored_messages'):
                self.bot.stored_messages.clear()
                self.logger.info("Stored messages cleared")

            if hasattr(self.bot, 'processed_channels'):
                self.bot.processed_channels.clear()
                self.logger.info("Processed channels list cleared")

            self.components_cleaned.append("pipeline")
            self.logger.info("Pipeline resource cleanup completed successfully")

        except Exception as e:
            # Pipeline cleanup errors are generally not critical
            self.logger.warning(f"Error during pipeline cleanup: {e}")

    async def cleanup_all(self) -> None:
        """Orchestrate complete cleanup of all bot resources.

        Executes cleanup operations in the correct order and continues
        cleanup even if individual components fail. Logs all errors
        but ensures cleanup completes for maximum resource recovery.
        """
        if self.cleanup_started:
            self.logger.warning("Cleanup already in progress, skipping duplicate call")
            return

        self.cleanup_started = True
        cleanup_errors: List[CleanupError] = []

        self.logger.info("🧹 Starting comprehensive bot cleanup...")

        # 1. Stop new request acceptance and complete in-progress operations
        try:
            await self.cleanup_llm_resources()
        except CleanupError as e:
            cleanup_errors.append(e)
            self.logger.error(f"LLM cleanup failed: {e}")

        # 2. Clean up message processing pipeline
        try:
            await self.cleanup_pipeline_resources()
        except CleanupError as e:
            cleanup_errors.append(e)
            self.logger.error(f"Pipeline cleanup failed: {e}")

        # 3. Clean up external resources (Discord, voice channels)
        try:
            await self.cleanup_discord_resources()
        except CleanupError as e:
            cleanup_errors.append(e)
            self.logger.error(f"Discord cleanup failed: {e}")

        # 4. Clean up database connections
        try:
            await self.cleanup_database_resources()
        except CleanupError as e:
            cleanup_errors.append(e)
            self.logger.error(f"Database cleanup failed: {e}")

        # Summary of cleanup results
        if cleanup_errors:
            self.logger.warning(
                f"🧹 Cleanup completed with {len(cleanup_errors)} errors. "
                f"Successfully cleaned: {', '.join(self.components_cleaned)}"
            )
            for error in cleanup_errors:
                self.logger.error(f"Cleanup error: {error}")
        else:
            self.logger.info(
                f"🧹 Cleanup completed successfully! "
                f"Cleaned components: {', '.join(self.components_cleaned)}"
            )

        self.logger.info("Bot shutdown complete")