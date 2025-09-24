import asyncio
import discord
from discord.ext import commands
from src.config.settings import settings
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from src.bot.rate_limiter import DiscordRateLimiter
from src.message_processing.storage import get_server_indexing_status
from src.setup import is_server_configured

if TYPE_CHECKING:
    from src.message_processing import MessagePipeline
    from src.ai.agents.dm_assistant import DMAssistant


class DiscordBot(commands.Bot):
    """Discord bot client for message indexing and processing.

    Handles Discord connection, message extraction, and temporary storage
    of messages for processing. Provides methods for both historical
    message fetching and real-time message monitoring.
    """

    def __init__(self) -> None:
        super().__init__(
            command_prefix=settings.COMMAND_PREFIX,
            intents=settings.get_intents,
            help_command=None,
        )
        # Pipeline coordination
        self.pipeline_ready = asyncio.Event()
        self.pipeline_ready.set()  # Initially ready
        self.message_pipeline: Optional["MessagePipeline"] = None
        self.batch_size = 1000
        
        # DMAssistant for conversation handling
        self.dm_assistant: Optional["DMAssistant"] = None
        self.queue_worker = None
        
        # Legacy storage (will be removed when pipeline fully implemented)
        self.stored_messages: List[Dict[str, Any]] = []
        self.processed_channels: List[int] = []
        
        # Rate limiting and logging
        self.rate_limiter = DiscordRateLimiter()
        self.logger = logging.getLogger(__name__)

    async def close(self) -> None:
        """Clean shutdown of bot connection."""
        # Clear message pipeline reference
        if self.message_pipeline:
            self.message_pipeline = None
            self.logger.info("Message pipeline cleared")
            
        
        # Clear queue worker
        if hasattr(self, 'queue_worker') and self.queue_worker:
            await self.queue_worker.stop()
            self.queue_worker = None
            self.logger.info("Queue worker stopped")
            
        # Clear DMAssistant reference
        if hasattr(self, 'dm_assistant') and self.dm_assistant:
            self.dm_assistant = None
            self.logger.info("DMAssistant cleared")

        await super().close()

    async def setup_hook(self) -> None:
        """Called when bot is starting up."""
        self.logger.info("Bot setup hook called - preparing to connect...")

    async def on_ready(self) -> None:
        """Event when bot connects to Discord."""
        self.logger.info(f"{self.user} has connected to Discord!")
        self.logger.info(f"Bot is in {len(self.guilds)} guild(s)")

        # Log available guilds and channels
        for guild in self.guilds:
            self.logger.info(
                f"Connected to guild: {guild.name} (ID: {guild.id})"
            )
            self.logger.debug(f"  - Text channels: {len(guild.text_channels)}")
            self.logger.debug(f"  - Total channels: {len(guild.channels)}")

    def get_all_channels(self) -> List[discord.TextChannel]:
        """Get all text channels the bot can access.

        Returns:
            List of all accessible Discord text channels across all guilds
        """
        # Flatten all text channels from all guilds into single list
        return [
            channel
            for guild in self.guilds
            for channel in guild.channels
            if isinstance(channel, discord.TextChannel)
        ]
    
    def get_channels_by_guild(self) -> Dict[int, List[discord.TextChannel]]:
        """Get text channels grouped by guild ID.

        Returns:
            Dictionary mapping guild IDs to lists of text channels
        """
        channels_by_guild = {}
        for guild in self.guilds:
            text_channels = [
                channel for channel in guild.channels
                if isinstance(channel, discord.TextChannel)
            ]
            if text_channels:
                channels_by_guild[guild.id] = text_channels
        return channels_by_guild

    async def get_channel_messages(
        self, channel_id: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get messages from a specific channel.

        Args:
            channel_id: Discord channel ID to fetch messages from
            limit: Maximum number of messages to fetch (default 100)

        Returns:
            List of extracted message data dictionaries
        """
        channel = self.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            self.logger.warning(
                f"Channel {channel_id} not found or not a text channel"
            )
            return []

        messages = []
        try:
            # Fetch messages from the channel
            async for message in channel.history(
                limit=limit, oldest_first=True
            ):
                message_data = self._extract_message_data(message)
                messages.append(message_data)

            self.logger.info(
                f"Fetched {len(messages)} messages from #{channel.name}"
            )
            return messages

        except discord.Forbidden as e:
            self.logger.warning(
                f"No permission to read messages in #{channel.name}: {e}"
            )
            return []
        except discord.HTTPException as e:
            self.logger.error(
                f"HTTP error fetching messages from #{channel.name}: {e}"
            )
            return []
        except discord.NotFound as e:
            self.logger.warning(f"Channel #{channel.name} not found: {e}")
            return []

    async def send_batch_to_pipeline(self, messages: List[Dict[str, Any]]) -> bool:
        """Send a batch of messages to pipeline and wait for completion.
        
        Implements backpressure by waiting for pipeline to finish processing
        before allowing the next batch to be sent.
        
        Args:
            messages: List of message data dictionaries to process
            
        Returns:
            True if batch processed successfully, False if failed
        """
        if not self.message_pipeline:
            self.logger.error("Message pipeline not available")
            return False
            
        if not messages:
            self.logger.info("No messages to send to pipeline")
            return True
        
        self.logger.info(f"Sending batch of {len(messages)} messages to pipeline")
        
        # Clear the ready event before processing
        self.pipeline_ready.clear()
        
        # Send batch to pipeline for processing
        success = await self.message_pipeline.process_messages(messages)
        
        # Wait for pipeline to signal completion
        await self.pipeline_ready.wait()
        
        if success:
            self.logger.info("Batch processing completed successfully")
        else:
            self.logger.error("Batch processing failed")
            
        return success
    
    async def resume_indexing_from_checkpoints(self) -> bool:
        """Resume message indexing from last indexed timestamps per server.
        
        Checks each server's indexing status and processes only messages newer 
        than the last indexed timestamp. Maintains server separation and 
        chronological ordering.
        
        Returns:
            True if all servers processed successfully, False if failed
        """
        if not self.message_pipeline:
            self.logger.error("Message pipeline not available for resumption processing")
            return False
            
        channels_by_guild = self.get_channels_by_guild()
        
        if not channels_by_guild:
            self.logger.info("No channels available for resumption processing")
            return True

        total_guilds = len(channels_by_guild)
        self.logger.info(f"Starting smart resumption for {total_guilds} servers...")

        try:
            overall_total_processed = 0
            
            # Process each server separately with resumption logic
            for guild_id, guild_channels in channels_by_guild.items():
                self.logger.info(f"Checking resumption status for server {guild_id}")

                # Check if server is configured (should already be configured at startup)
                if not is_server_configured(str(guild_id)):
                    self.logger.warning(f"Skipping historical processing for unconfigured server {guild_id}")
                    continue

                # Get resumption info for this server
                server_status = get_server_indexing_status(guild_id)
                
                self.logger.info(f"Server {guild_id} status: {server_status['status']}, "
                               f"{server_status['message_count']} messages indexed")
                
                server_total_processed = 0
                
                # Determine processing strategy based on server status
                if server_status['needs_full_processing']:
                    # Server needs full historical processing
                    self.logger.info(f"Server {guild_id}: Full historical processing required")
                    
                    # Process channels in batches within this server
                    for i in range(0, len(guild_channels), 5):  # Process 5 channels at a time
                        channel_batch = guild_channels[i:i+5]
                        
                        self.logger.info(f"Server {guild_id}: Full processing channels {i+1}-{min(i+5, len(guild_channels))} of {len(guild_channels)}")
                        
                        # Fetch all historical messages from this batch of channels
                        raw_messages = await self.rate_limiter.batch_fetch_messages(
                            channels=channel_batch,
                            messages_per_channel=1000,
                            max_concurrent_channels=5,
                        )
                        
                        if raw_messages:
                            # Process raw messages into structured data
                            batch_messages = [self._extract_message_data(msg) for msg in raw_messages]
                            
                            # Send batch to pipeline and wait for completion
                            success = await self.send_batch_to_pipeline(batch_messages)
                            
                            if not success:
                                self.logger.error(f"Failed to process full historical batch for server {guild_id}")
                                return False
                            
                            server_total_processed += len(batch_messages)
                        
                        # Update processed channels list
                        for channel in channel_batch:
                            self.processed_channels.append(channel.id)
                
                elif server_status['resumption_recommended']:
                    # Server can resume from last timestamp
                    last_timestamp = server_status['last_indexed_timestamp']
                    self.logger.info(f"Server {guild_id}: Resuming from {last_timestamp}")
                    
                    # Process channels in batches within this server
                    for i in range(0, len(guild_channels), 5):  # Process 5 channels at a time
                        channel_batch = guild_channels[i:i+5]
                        
                        self.logger.info(f"Server {guild_id}: Resumption processing channels {i+1}-{min(i+5, len(guild_channels))} of {len(guild_channels)}")
                        
                        # Fetch messages newer than last indexed timestamp
                        raw_messages = await self.rate_limiter.batch_fetch_messages_after_timestamp(
                            channels=channel_batch,
                            after_timestamp=last_timestamp,
                            messages_per_channel=1000,
                            max_concurrent_channels=5,
                        )
                        
                        if raw_messages:
                            # Process raw messages into structured data
                            batch_messages = [self._extract_message_data(msg) for msg in raw_messages]
                            
                            # Send batch to pipeline and wait for completion
                            success = await self.send_batch_to_pipeline(batch_messages)
                            
                            if not success:
                                self.logger.error(f"Failed to process resumption batch for server {guild_id}")
                                return False
                            
                            server_total_processed += len(batch_messages)
                        
                        # Update processed channels list
                        for channel in channel_batch:
                            self.processed_channels.append(channel.id)
                
                else:
                    # Server is fully up to date
                    self.logger.info(f"Server {guild_id}: Already up to date, skipping")
                    # Still mark channels as processed for tracking
                    for channel in guild_channels:
                        self.processed_channels.append(channel.id)
                
                overall_total_processed += server_total_processed
                self.logger.info(f"Server {guild_id} resumption completed. Processed {server_total_processed} new messages")

            self.logger.info(f"Smart resumption completed successfully. Total processed: {overall_total_processed} new messages")
            return True
            
        except (discord.HTTPException, asyncio.TimeoutError, MemoryError, 
                ValueError, IndexError, RuntimeError) as e:
            self.logger.error(f"Error during smart resumption processing: {e}")
            return False



    def _extract_message_data(self, message: discord.Message) -> Dict[str, Any]:
        """Extract relevant data from a Discord message.

        Args:
            message: Discord message object to extract data from

        Returns:
            Dictionary containing structured message data
        """
        # Extract guild info with None fallback
        guild_id = message.guild.id if message.guild else None
        guild_name = message.guild.name if message.guild else None

        # Handle different channel types
        if isinstance(message.channel, discord.DMChannel):
            # For DM channels, create a descriptive name
            other_user = message.channel.recipient
            channel_name = f"DM with {other_user.name}" if other_user else "DM"
        else:
            # For guild channels (TextChannel, etc.)
            channel_name = getattr(message.channel, 'name', 'Unknown Channel')

        # Extract additional channel metadata for guild channels
        channel_data = {"id": message.channel.id, "name": channel_name}
        if hasattr(message.channel, 'type'):
            channel_data["type"] = str(message.channel.type)
        if hasattr(message.channel, 'category_id'):
            channel_data["category_id"] = message.channel.category_id
        if hasattr(message.channel, 'position'):
            channel_data["position"] = message.channel.position

        # Extract additional guild metadata
        guild_data = {"id": guild_id, "name": guild_name}
        if message.guild:
            if hasattr(message.guild, 'icon'):
                guild_data["icon"] = str(message.guild.icon) if message.guild.icon else None
            if hasattr(message.guild, 'member_count'):
                guild_data["member_count"] = message.guild.member_count
            if hasattr(message.guild, 'features'):
                guild_data["features"] = message.guild.features

        # Extract reply reference if present
        reference_data = None
        if message.reference:
            reference_data = {"message_id": message.reference.message_id}

        return {
            "id": message.id,
            "content": message.content,
            "author": {
                "id": message.author.id,
                "name": message.author.name,
                "display_name": message.author.display_name,
                "global_name": getattr(message.author, 'global_name', None),
                "nick": getattr(message.author, 'nick', None),
                "discriminator": getattr(message.author, 'discriminator', None),
                "bot": message.author.bot,
                "system": getattr(message.author, 'system', False)
            },
            "channel": channel_data,
            "guild": guild_data,
            "timestamp": message.created_at.isoformat(),
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "pinned": message.pinned,
            "reference": reference_data,
            "attachments": [att.url for att in message.attachments],
            "has_embeds": len(message.embeds) > 0,
            "type": str(message.type),
        }
