import discord
from discord.ext import commands
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import DiscordBot


async def on_ready_handler(bot: "DiscordBot") -> None:
    """Handle bot ready event - start monitoring for new messages.
    
    Triggers historical message processing and transitions to real-time monitoring.
    
    Args:
        bot: DiscordBot instance with message processing capabilities
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Bot is ready! Now monitoring for new messages... ===")
    
    # Log available channels for info
    channels = bot.get_all_channels()
    logger.info(f"📡 Monitoring {len(channels)} channels for new messages")


async def on_message_handler(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle new incoming messages.
    
    Filters out bot messages and processes new user messages for storage.
    
    Args:
        bot: DiscordBot instance for message storage
        message: Discord message object to process
    """
    logger = logging.getLogger(__name__)
    
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Extract and store the new message
    message_data = bot._extract_message_data(message)
    bot.stored_messages.append(message_data)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"📨 New message: #{message.channel.name} - {message.author.name}: {content_preview}")


def setup_bot_actions(bot: "DiscordBot") -> None:
    """Setup event handlers for the bot.
    
    Registers Discord event handlers for connection and message processing.
    
    Args:
        bot: DiscordBot instance to register handlers with
    """
    logger = logging.getLogger(__name__)
    
    @bot.event
    async def on_ready() -> None:
        """Event when bot connects to Discord."""
        await on_ready_handler(bot)
    
    @bot.event
    async def on_message(message: discord.Message) -> None:
        """Event when new message is received."""
        await on_message_handler(bot, message)
    
    logger.info("✅ Bot event handlers registered")
