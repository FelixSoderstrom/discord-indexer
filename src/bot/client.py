import discord
from discord.ext import commands
from src.config.settings import settings
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..message_processing import MessagePipeline


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
            help_command=None
        )
        # Storage for messages (will be replaced with database later)
        self.stored_messages: List[Dict[str, Any]] = []
        self.processed_channels: List[int] = []
        self.message_pipeline: Optional["MessagePipeline"] = None
        self.logger = logging.getLogger(__name__)

    async def close(self) -> None:
        """Clean shutdown of bot connection."""
        # Clear message pipeline reference
        if self.message_pipeline:
            self.message_pipeline = None
            self.logger.info("Message pipeline cleared")
        
        await super().close()
    
    async def setup_hook(self) -> None:
        """Called when bot is starting up."""
        self.logger.info("Bot setup hook called - preparing to connect...")
    
    async def on_ready(self) -> None:
        """Event when bot connects to Discord."""
        self.logger.info(f'{self.user} has connected to Discord!')
        self.logger.info(f'Bot is in {len(self.guilds)} guild(s)')
        
        # Log available guilds and channels
        for guild in self.guilds:
            self.logger.info(f'Connected to guild: {guild.name} (ID: {guild.id})')
            self.logger.debug(f'  - Text channels: {len(guild.text_channels)}')
            self.logger.debug(f'  - Total channels: {len(guild.channels)}')
    
    def get_all_channels(self) -> List[discord.TextChannel]:
        """Get all text channels the bot can access.
        
        Returns:
            List of all accessible Discord text channels across all guilds
        """
        # Flatten all text channels from all guilds into single list
        return [
            channel for guild in self.guilds 
            for channel in guild.channels 
            if isinstance(channel, discord.TextChannel)
        ]
    
    async def get_channel_messages(self, channel_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages from a specific channel.
        
        Args:
            channel_id: Discord channel ID to fetch messages from
            limit: Maximum number of messages to fetch (default 100)
            
        Returns:
            List of extracted message data dictionaries
        """
        channel = self.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            self.logger.warning(f"Channel {channel_id} not found or not a text channel")
            return []
        
        messages = []
        try:
            # Fetch messages from the channel
            async for message in channel.history(limit=limit, oldest_first=True):
                message_data = self._extract_message_data(message)
                messages.append(message_data)
            
            self.logger.info(f"Fetched {len(messages)} messages from #{channel.name}")
            return messages
            
        except discord.Forbidden as e:
            self.logger.warning(f"No permission to read messages in #{channel.name}: {e}")
            return []
        except discord.HTTPException as e:
            self.logger.error(f"HTTP error fetching messages from #{channel.name}: {e}")
            return []
        except discord.NotFound as e:
            self.logger.warning(f"Channel #{channel.name} not found: {e}")
            return []
    
    async def get_all_historical_messages(self) -> List[Dict[str, Any]]:
        """Fetch all historical messages from all accessible channels.
        
        Returns:
            List of all extracted message data from accessible channels
        """
        all_messages = []
        channels = self.get_all_channels()
        
        self.logger.info(f"Processing {len(channels)} channels for historical messages...")
        
        for channel in channels:
            self.logger.info(f"Fetching messages from #{channel.name}...")
            channel_messages = await self.get_channel_messages(channel.id, limit=1000)
            all_messages.extend(channel_messages)
            self.processed_channels.append(channel.id)
        
        self.logger.info(f"Total messages fetched: {len(all_messages)}")
        self.stored_messages.extend(all_messages)
        return all_messages
    
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
        
        return {
            'id': message.id,
            'content': message.content,
            'author': {
                'id': message.author.id,
                'name': message.author.name,
                'display_name': message.author.display_name
            },
            'channel': {
                'id': message.channel.id,
                'name': message.channel.name
            },
            'guild': {
                'id': guild_id,
                'name': guild_name
            },
            'timestamp': message.created_at.isoformat(),
            'attachments': [att.url for att in message.attachments],
            'has_embeds': len(message.embeds) > 0,
            'message_type': str(message.type)
        }
