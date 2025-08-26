import discord
from discord.ext import commands
import logging
import sys
from typing import TYPE_CHECKING

from ..message_processing import MessagePipeline
from .dm_commands import handle_dm_message
from .voice_manager import handle_voice_state_update

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


async def on_message_handler(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle new incoming messages.
    
    Routes DM messages to command handler, server messages to the unified pipeline.
    
    Args:
        bot: DiscordBot instance with message processing pipeline
        message: Discord message object to process
    """
    logger = logging.getLogger(__name__)
    
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Route DM messages to command handler (bypass pipeline)
    if message.guild is None:  # DM message
        await handle_dm_message(bot, message)
        return
    
    # For server messages, continue with pipeline processing
    # Check if pipeline is available
    if not hasattr(bot, 'message_pipeline') or not bot.message_pipeline:
        logger.critical("❌ Message pipeline not available - application is fundamentally broken")
        logger.critical("🛑 Shutting down application - cannot process messages without pipeline")
        await bot.close()
        sys.exit(1)
    
    # Extract message data and wrap in list for unified pipeline interface
    message_data = bot._extract_message_data(message)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"📨 Processing new message: #{message.channel.name} - {message.author.name}: {content_preview}")
    
    # Send single message as batch to pipeline (unified interface)
    success = await bot.send_batch_to_pipeline([message_data])
    
    if success:
        logger.debug("✅ Message processed successfully through pipeline")
    else:
        logger.critical("❌ Failed to process message through pipeline - application is fundamentally broken")
        logger.critical("🛑 Shutting down application - cannot continue without functional pipeline")
        await bot.close()
        sys.exit(1)


async def on_voice_state_update_handler(
    bot: "DiscordBot", 
    member: discord.Member, 
    before: discord.VoiceState, 
    after: discord.VoiceState
) -> None:
    """Handle voice state updates for automatic session cleanup.
    
    Delegates to voice manager for business logic.
    
    Args:
        bot: DiscordBot instance
        member: Member whose voice state changed
        before: Voice state before the change
        after: Voice state after the change
    """
    await handle_voice_state_update(bot, member, before, after)


def setup_bot_actions(bot: "DiscordBot") -> None:
    """Setup event handlers for the bot.
    
    Registers Discord event handlers for connection, message processing, and voice functionality.
    
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
    
    @bot.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """Event when user's voice state changes."""
        await on_voice_state_update_handler(bot, member, before, after)
    
    logger.info("✅ Bot event handlers registered")
