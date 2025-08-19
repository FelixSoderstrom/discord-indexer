import discord
from discord.ext import commands
from src.config.settings import settings
import logging
from typing import List, Dict, Any


class DiscordBot(commands.Bot):
    """Discord bot client for message indexing and processing."""
    
    def __init__(self):
        super().__init__(
            command_prefix=settings.COMMAND_PREFIX,
            intents=settings.get_intents,
            help_command=None
        )
        # Storage for messages (will be replaced with database later)
        self.stored_messages: List[Dict[str, Any]] = []
        self.processed_channels: List[int] = []
    
    async def setup_hook(self):
        """Called when bot is starting up."""
        logging.info("Bot setup hook called - preparing to connect...")
    
    async def on_ready(self):
        """Event when bot connects to Discord."""
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guild(s)')
        
        # Log available guilds and channels
        for guild in self.guilds:
            print(f'Connected to guild: {guild.name} (ID: {guild.id})')
            print(f'  - Text channels: {len(guild.text_channels)}')
            print(f'  - Total channels: {len(guild.channels)}')
    
    def get_all_channels(self) -> List[discord.TextChannel]:
        """Get all text channels the bot can access."""
        all_channels = []
        for guild in self.guilds:
            # Get text channels (excluding voice, categories, etc.)
            text_channels = [channel for channel in guild.channels 
                           if isinstance(channel, discord.TextChannel)]
            all_channels.extend(text_channels)
        return all_channels
    
    async def get_channel_messages(self, channel_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages from a specific channel."""
        channel = self.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            logging.warning(f"Channel {channel_id} not found or not a text channel")
            return []
        
        messages = []
        try:
            # Fetch messages from the channel
            async for message in channel.history(limit=limit, oldest_first=True):
                message_data = self._extract_message_data(message)
                messages.append(message_data)
            
            logging.info(f"Fetched {len(messages)} messages from #{channel.name}")
            return messages
            
        except discord.Forbidden:
            logging.warning(f"No permission to read messages in #{channel.name}")
            return []
        except Exception as e:
            logging.error(f"Error fetching messages from #{channel.name}: {e}")
            return []
    
    async def get_all_historical_messages(self) -> List[Dict[str, Any]]:
        """Fetch all historical messages from all accessible channels."""
        all_messages = []
        channels = self.get_all_channels()
        
        print(f"Processing {len(channels)} channels for historical messages...")
        
        for channel in channels:
            print(f"  Fetching messages from #{channel.name}...")
            channel_messages = await self.get_channel_messages(channel.id, limit=1000)
            all_messages.extend(channel_messages)
            self.processed_channels.append(channel.id)
        
        print(f"Total messages fetched: {len(all_messages)}")
        self.stored_messages.extend(all_messages)
        return all_messages
    
    def _extract_message_data(self, message: discord.Message) -> Dict[str, Any]:
        """Extract relevant data from a Discord message."""
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
                'id': message.guild.id if message.guild else None,
                'name': message.guild.name if message.guild else None
            },
            'timestamp': message.created_at.isoformat(),
            'attachments': [att.url for att in message.attachments],
            'has_embeds': len(message.embeds) > 0,
            'message_type': str(message.type)
        }
