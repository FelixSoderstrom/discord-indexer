import discord
from discord.ext import commands
import logging
import sys
from typing import TYPE_CHECKING

from ..message_processing import MessagePipeline

if TYPE_CHECKING:
    from .client import DiscordBot


async def on_ready_handler(bot: "DiscordBot") -> None:
    """Handle bot ready event - start historical processing and real-time monitoring.
    
    Initializes pipeline, processes historical messages, then transitions to real-time monitoring.
    
    Args:
        bot: DiscordBot instance with message processing capabilities
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Bot is ready! Starting message processing... ===")
    
    # Initialize message pipeline with coordination event
    logger.info("🔧 Initializing message processing pipeline...")
    bot.message_pipeline = MessagePipeline(completion_event=bot.pipeline_ready)
    logger.info("✅ Message pipeline initialized successfully")
    
    # Process historical messages through pipeline
    logger.info("📜 Starting historical message processing through pipeline...")
    historical_success = await bot.process_historical_messages_through_pipeline()
    
    if historical_success:
        logger.info("✅ Historical message processing completed successfully")
        logger.info("📡 Now monitoring for new real-time messages...")
        
        # Log available channels for info
        channels = bot.get_all_channels()
        logger.info(f"📡 Monitoring {len(channels)} channels for new messages")
    else:
        logger.critical("❌ Historical message processing failed - shutting down")
        await bot.close()
        sys.exit(1)


async def handle_dm_message(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle direct messages to the bot for commands and interactions.
    
    DM messages are NOT indexed and bypass the message processing pipeline entirely.
    
    Args:
        bot: DiscordBot instance
        message: Discord DM message object
    """
    logger = logging.getLogger(__name__)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"💬 Received DM from {message.author.name}: {content_preview}")
    
    # Basic command handling - expand this as needed
    content = message.content.strip().lower()
    
    if content.startswith('help') or content == '?':
        await message.channel.send(
            "🤖 **Discord Indexer Bot**\n\n"
            "I index messages from server channels to enable AI-powered search.\n\n"
            "**Available commands:**\n"
            "• `help` - Show this help message\n"
            "• `status` - Show bot status\n"
            "• `info` - Show bot information\n\n"
            "Note: Only server messages are indexed. DMs are private and never stored."
        )
    elif content == 'status':
        guild_count = len(bot.guilds)
        channel_count = len(bot.get_all_channels())
        await message.channel.send(
            f"📊 **Bot Status**\n\n"
            f"• Connected to {guild_count} server(s)\n"
            f"• Monitoring {channel_count} text channel(s)\n"
            f"• Pipeline status: {'✅ Active' if bot.message_pipeline else '❌ Inactive'}"
        )
    elif content == 'info':
        await message.channel.send(
            "ℹ️ **About Discord Indexer Bot**\n\n"
            "I help build searchable indexes of Discord server messages for AI-powered search and analysis.\n\n"
            "• Server messages → Indexed and searchable\n"
            "• DM messages → Private, never indexed\n"
            "• Powered by advanced NLP and vector embeddings"
        )
    else:
        await message.channel.send(
            f"🤔 I don't understand that command. Try `help` to see available commands."
        )


async def on_message_handler(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle new incoming messages with routing based on message type.
    
    Routes messages to appropriate handlers:
    - Server/guild messages → indexing pipeline
    - DM messages → command handler (never indexed)
    
    Args:
        bot: DiscordBot instance with message processing pipeline
        message: Discord message object to process
    """
    logger = logging.getLogger(__name__)
    
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Route based on message type
    if isinstance(message.channel, discord.DMChannel):
        # Handle DMs separately - they bypass indexing entirely
        await handle_dm_message(bot, message)
        return
    
    # Handle server/guild messages for indexing
    if not message.guild:
        logger.warning("Received non-DM message without guild - skipping")
        return
    
    # Check if pipeline is available for server messages
    if not hasattr(bot, 'message_pipeline') or not bot.message_pipeline:
        logger.critical("❌ Message pipeline not available - application is fundamentally broken")
        logger.critical("🛑 Shutting down application - cannot process messages without pipeline")
        await bot.close()
        sys.exit(1)
    
    # Extract message data and wrap in list for unified pipeline interface
    message_data = bot._extract_message_data(message)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"📨 Processing server message: #{message.channel.name} - {message.author.name}: {content_preview}")
    
    # Send single message as batch to pipeline (unified interface)
    success = await bot.send_batch_to_pipeline([message_data])
    
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
