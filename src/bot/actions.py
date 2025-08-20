import discord
from discord.ext import commands
import logging
import sys
from typing import TYPE_CHECKING

from ..message_processing import MessagePipeline

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
    
    # Initialize message pipeline
    logger.info("🔧 Initializing message processing pipeline...")
    bot.message_pipeline = MessagePipeline()
    logger.info("✅ Message pipeline initialized successfully")
    
    # Log available channels for info
    channels = bot.get_all_channels()
    logger.info(f"📡 Monitoring {len(channels)} channels for new messages")


async def on_message_handler(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle new incoming messages.
    
    Filters out bot messages and processes new user messages through the pipeline.
    
    Args:
        bot: DiscordBot instance with message processing pipeline
        message: Discord message object to process
    """
    logger = logging.getLogger(__name__)
    
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Check if pipeline is available
    if not hasattr(bot, 'message_pipeline') or not bot.message_pipeline:
        logger.critical("❌ Message pipeline not available - application is fundamentally broken")
        logger.critical("🛑 Shutting down application - cannot process messages without pipeline")
        await bot.close()
        sys.exit(1)
    
    # Extract message data and process through pipeline
    message_data = bot._extract_message_data(message)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"📨 Processing new message: #{message.channel.name} - {message.author.name}: {content_preview}")
    
    # Process message through pipeline
    success = bot.message_pipeline.process_message(message_data)
    
    if success:
        logger.debug("✅ Message processed successfully through pipeline")
    else:
        logger.critical("❌ Failed to process message through pipeline - application is fundamentally broken")
        logger.critical("🛑 Shutting down application - cannot continue without functional pipeline")
        await bot.close()
        sys.exit(1)


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
