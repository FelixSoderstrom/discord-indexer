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
    """Handle direct messages to the bot that are not commands.
    
    DM messages are NOT indexed and bypass the message processing pipeline entirely.
    Only non-command DMs reach this handler since commands are processed by the commands extension.
    
    Args:
        bot: DiscordBot instance
        message: Discord DM message object
    """
    logger = logging.getLogger(__name__)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"💬 Received non-command DM from {message.author.name}: {content_preview}")
    
    # If someone sends a DM without using a command, provide helpful guidance
    await message.channel.send(
        "👋 Hello! I'm the Discord Indexer Bot.\n\n"
        "To interact with me, please use commands with the `!` prefix:\n"
        "• `!help` - Show available commands\n"
        "• `!status` - Show bot status\n"
        "• `!info` - Show bot information\n\n"
        "Note: Only server messages are indexed. DMs are private and never stored."
    )


async def on_message_handler(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle new incoming messages with routing based on message type.
    
    Routes messages to appropriate handlers:
    - Commands (with ! prefix) → handled by commands extension automatically
    - Server/guild messages → indexing pipeline
    - Non-command DM messages → helpful guidance (never indexed)
    
    Args:
        bot: DiscordBot instance with message processing pipeline
        message: Discord message object to process
    """
    logger = logging.getLogger(__name__)
    
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Handle DM messages
    if isinstance(message.channel, discord.DMChannel):
        # Check if this is a command - if so, let the commands extension handle it
        if message.content.startswith(bot.command_prefix):
            # Command will be processed by bot.process_commands() after this handler
            return
        else:
            # Handle non-command DMs - provide helpful guidance
            await handle_dm_message(bot, message)
        return
    
    # Handle server/guild messages for indexing
    if not message.guild:
        logger.warning("Received non-DM message without guild - skipping")
        return
    
    # Skip server commands - they get processed by the commands extension
    if message.content.startswith(bot.command_prefix):
        # Command will be processed by bot.process_commands() after this handler
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
    """Setup event handlers and commands for the bot.
    
    Registers Discord event handlers for connection and message processing,
    and sets up proper command handlers using the commands extension.
    
    Args:
        bot: DiscordBot instance to register handlers with
    """
    logger = logging.getLogger(__name__)
    
    # ===== EVENT HANDLERS =====
    @bot.event
    async def on_ready() -> None:
        """Event when bot connects to Discord."""
        await on_ready_handler(bot)
    
    @bot.event
    async def on_message(message: discord.Message) -> None:
        """Event when new message is received."""
        await on_message_handler(bot, message)
        # Process commands after handling the message
        await bot.process_commands(message)
    
    # ===== COMMAND HANDLERS =====
    @bot.command(name='help')
    async def help_command(ctx: commands.Context) -> None:
        """Show available bot commands and information."""
        embed = discord.Embed(
            title="🤖 Discord Indexer Bot",
            description="I index messages from server channels to enable AI-powered search.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 Available Commands",
            value=(
                "`!help` - Show this help message\n"
                "`!status` - Show bot status and statistics\n"
                "`!info` - Show detailed bot information"
            ),
            inline=False
        )
        embed.add_field(
            name="🔒 Privacy Notice",
            value="Only server messages are indexed. DMs are private and never stored.",
            inline=False
        )
        embed.set_footer(text="Use commands in DMs or servers")
        
        await ctx.send(embed=embed)
    
    @bot.command(name='status')
    async def status_command(ctx: commands.Context) -> None:
        """Show current bot status and statistics."""
        guild_count = len(bot.guilds)
        channel_count = len(bot.get_all_channels())
        pipeline_status = "✅ Active" if bot.message_pipeline else "❌ Inactive"
        
        embed = discord.Embed(
            title="📊 Bot Status",
            color=discord.Color.green()
        )
        embed.add_field(name="Servers", value=str(guild_count), inline=True)
        embed.add_field(name="Channels", value=str(channel_count), inline=True)
        embed.add_field(name="Pipeline", value=pipeline_status, inline=True)
        embed.add_field(
            name="Processed Channels", 
            value=str(len(bot.processed_channels)), 
            inline=True
        )
        embed.add_field(
            name="Messages in Memory", 
            value=str(len(bot.stored_messages)), 
            inline=True
        )
        embed.set_footer(text=f"Latency: {round(bot.latency * 1000)}ms")
        
        await ctx.send(embed=embed)
    
    @bot.command(name='info')
    async def info_command(ctx: commands.Context) -> None:
        """Show detailed information about the bot."""
        embed = discord.Embed(
            title="ℹ️ About Discord Indexer Bot",
            description="Advanced Discord message indexing system for AI-powered search and analysis.",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🎯 Purpose",
            value="Build searchable indexes of Discord server messages",
            inline=False
        )
        embed.add_field(
            name="🔄 Message Flow",
            value=(
                "• **Server messages** → Indexed and searchable\n"
                "• **DM messages** → Private, never indexed\n"
                "• **Commands** → Processed instantly"
            ),
            inline=False
        )
        embed.add_field(
            name="🧠 Technology",
            value="Powered by advanced NLP and vector embeddings",
            inline=False
        )
        embed.set_footer(text="Developed for intelligent Discord data analysis")
        
        await ctx.send(embed=embed)
    
    # ===== COMMAND ERROR HANDLING =====
    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors gracefully."""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                "❓ **Command not found!**\n"
                f"Use `!help` to see available commands."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ **Missing required argument!**\n"
                f"Use `!help` for command usage information."
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"❌ **Invalid argument!**\n"
                f"Use `!help` for command usage information."
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏰ **Command on cooldown!**\n"
                f"Try again in {error.retry_after:.1f} seconds."
            )
        else:
            logger.error(f"Unexpected command error: {error}")
            await ctx.send(
                "❌ **An unexpected error occurred!**\n"
                "The error has been logged for investigation."
            )
    
    logger.info("✅ Bot event handlers and commands registered")
