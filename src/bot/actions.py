import discord
from discord.ext import commands
import logging
import sys
import os
import re
from typing import TYPE_CHECKING
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass
from src.message_processing import MessagePipeline
from src.llm.agents.configuration_agent import ConfigurationAgent
from src.llm.agents.langchain_dm_assistant import LangChainDMAssistant
from src.llm.agents.queue_worker import initialize_queue_worker
from src.db.setup_db import get_db
from src.llm.agents.conversation_queue import get_conversation_queue
from src.db.conversation_db import get_conversation_db
from src.exceptions.message_processing import LLMProcessingError


@dataclass
class ServerOption:
    """Available server option for user selection."""

    server_id: str
    server_name: str
    last_indexed: Optional[datetime] = None
    message_count: int = 0


if TYPE_CHECKING:
    from src.bot.client import DiscordBot


async def on_ready_handler(bot: "DiscordBot") -> None:
    """Handle bot ready event - start historical processing and real-time monitoring.

    Initializes pipeline, processes historical messages, then transitions to real-time monitoring.

    Args:
        bot: DiscordBot instance with message processing capabilities
    """
    logger = logging.getLogger(__name__)

    # Log guild connection information (replicated from client.py to avoid circular calls)
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} guild(s)")

    # Log available guilds and channels
    for guild in bot.guilds:
        logger.info(f"Connected to guild: {guild.name} (ID: {guild.id})")
        logger.debug(f"  - Text channels: {len(guild.text_channels)}")
        logger.debug(f"  - Total channels: {len(guild.channels)}")

    logger.info("=== Bot is ready! Starting message processing... ===")

    # Initialize message pipeline with coordination event
    logger.info("🔧 Initializing message processing pipeline...")
    bot.message_pipeline = MessagePipeline(completion_event=bot.pipeline_ready)
    logger.info("✅ Message pipeline initialized successfully")

    # Initialize LangChain DMAssistant for conversation handling
    logger.info("🤖 Initializing LangChain DMAssistant...")
    try:
        bot.dm_assistant = LangChainDMAssistant()
        logger.info("✅ LangChain DMAssistant base components initialized")

        # Verify model is available and healthy (async - non-blocking)
        logger.info(
            "🔍 Running async LLM health check (may take time for initial model load)..."
        )
        health_check_passed = await bot.dm_assistant.health_check_async(
            timeout_seconds=120.0
        )

        if health_check_passed:
            logger.info(
                "✅ LangChain DMAssistant model health check passed - ready for requests"
            )
        else:
            logger.error("❌ LangChain DMAssistant model health check failed")
            raise LLMProcessingError(
                "LangChain DMAssistant model not available or not responsive"
            )

        # Session manager removed in Phase 1 - now using stateless queue-based processing
        logger.info(
            "✅ Using stateless queue-based processing (no session manager needed)"
        )

        # Initialize queue worker with LangChain
        logger.info("⚡ Starting LangChain conversation queue worker...")
        queue_worker = initialize_queue_worker(use_langchain=True)
        await queue_worker.start()
        bot.queue_worker = queue_worker  # Store reference for cleanup
        logger.info("✅ LangChain queue worker started successfully")

    except (ImportError, RuntimeError, ConnectionError, OSError) as e:
        logger.critical(f"❌ Failed to initialize DMAssistant: {e}")
        logger.critical("🛑 Shutting down - DMAssistant is required for bot operation")
        await bot.close()
        sys.exit(1)

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

    Provides helpful guidance about available commands since we now use
    stateless queue-based processing instead of persistent sessions.

    Args:
        bot: DiscordBot instance
        message: Discord DM message object
    """
    logger = logging.getLogger(__name__)

    content_preview = (
        message.content[:30] + "..." if len(message.content) > 30 else message.content
    )
    logger.info(
        f"💬 Received non-command DM from {message.author.name}: {content_preview}"
    )

    # Provide helpful guidance for stateless interaction model
    await message.channel.send(
        "👋 Hello! I'm the Discord Indexer Bot.\n\n"
        "To ask me a question, use:\n"
        "• `!ask <your question>` - Ask me anything about your servers\n"
        "• `!help` - Show all available commands\n"
        "• `!status` - Show bot status\n\n"
        "Each `!ask` command is processed independently in a fair queue.\n"
        "Your conversation history is preserved in the database for context.\n\n"
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
            try:
                await handle_dm_message(bot, message)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound) as e:
                logger.error(
                    f"Discord error handling DM from {message.author.name}: {e}"
                )
            except (asyncio.TimeoutError, ConnectionError) as e:
                logger.error(
                    f"Connection error handling DM from {message.author.name}: {e}"
                )
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
    if not hasattr(bot, "message_pipeline") or not bot.message_pipeline:
        logger.critical(
            "❌ Message pipeline not available - application is fundamentally broken"
        )
        logger.critical(
            "🛑 Shutting down application - cannot process messages without pipeline"
        )
        await bot.close()
        sys.exit(1)

    # Check if server is configured before indexing messages
    server_id = str(message.guild.id)

    if not ConfigurationAgent.is_server_configured(server_id):
        logger.debug(
            f"Skipping message indexing for unconfigured server {message.guild.name} ({server_id})"
        )
        return

    # Extract message data and wrap in list for unified pipeline interface
    message_data = bot._extract_message_data(message)

    content_preview = (
        message.content[:30] + "..." if len(message.content) > 30 else message.content
    )
    logger.info(
        f"📨 Processing server message: #{message.channel.name} - {message.author.name}: {content_preview}"
    )

    # Send single message as batch to pipeline (unified interface)
    success = await bot.send_batch_to_pipeline([message_data])

    if success:
        logger.debug("✅ Message processed successfully through pipeline")
    else:
        logger.critical(
            "❌ Failed to process message through pipeline - application is fundamentally broken"
        )
        logger.critical(
            "🛑 Shutting down application - cannot continue without functional pipeline"
        )
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

    # ===== HELPER FUNCTIONS =====

    async def _get_mutual_servers_with_data(
        bot: "DiscordBot", user_id: int
    ) -> List[ServerOption]:
        """Get servers shared between bot and user, with indexing data.

        Args:
            bot: DiscordBot instance
            user_id: Discord user ID

        Returns:
            List of ServerOption objects with indexing information
        """

        mutual_servers = []

        # Find servers where both bot and user are members
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:  # User is in this server
                server_id = str(guild.id)
                server_name = guild.name

                # Check if this server has indexed data
                try:
                    # Check if database directory exists
                    db_path = os.path.join(
                        "src", "db", "databases", server_id, "chroma_data"
                    )

                    if os.path.exists(db_path):
                        # Get ChromaDB client and check message count
                        client = get_db(int(server_id))
                        collection = client.get_or_create_collection(
                            name="messages", metadata={"server_id": server_id}
                        )

                        message_count = collection.count()

                        # If no messages, skip this server
                        if message_count == 0:
                            continue

                        # Try to determine last indexed date
                        # This is a simple approach - could be enhanced
                        last_indexed = datetime.now()  # Default to now
                        if os.path.exists(db_path):
                            # Use directory modification time as proxy
                            last_indexed = datetime.fromtimestamp(
                                os.path.getmtime(db_path)
                            )

                        mutual_servers.append(
                            ServerOption(
                                server_id=server_id,
                                server_name=server_name,
                                last_indexed=last_indexed,
                                message_count=message_count,
                            )
                        )

                except (
                    OSError,
                    FileNotFoundError,
                    PermissionError,
                    ValueError,
                    ImportError,
                    AttributeError,
                    KeyError,
                    TypeError,
                ) as e:
                    # Log error but continue - this server just won't be available
                    logger.warning(
                        f"Error checking indexing data for server {server_id} ({server_name}): {e}"
                    )
                    continue

        # Sort by message count (most active servers first)
        mutual_servers.sort(key=lambda x: x.message_count, reverse=True)

        return mutual_servers

    # _handle_server_selection_response removed in Phase 1 - now using direct server selection in !ask command

    # ===== COMMAND HANDLERS =====
    @bot.command(name="ask")
    async def ask_command(ctx: commands.Context, *, message: str = None) -> None:
        """Ask the DMAssistant a question (stateless queue-based processing)."""
        if not message:
            await ctx.send(
                "❓ **Usage**: `!ask <your question>`\nExample: `!ask What did PM say about the standup?`"
            )
            return

        # Only work in DMs
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(
                "🔒 **DM Only**: The `!ask` command only works in direct messages for privacy."
            )
            return

        # Import systems
        queue = get_conversation_queue()
        user_id = str(ctx.author.id)

        # Check if user already has a request queued
        if queue.is_user_queued(user_id):
            await ctx.send(
                "⏳ **Already Processing**: You already have a request in the queue. Please wait for it to complete."
            )
            return

        # Parse server selection from message if present [server] format
        server_selection = None
        actual_message = message
        server_match = re.match(r"^\[([^\]]+)\]\s*(.*)", message)
        if server_match:
            server_selection = server_match.group(1).strip()
            actual_message = server_match.group(2).strip()

            if not actual_message:
                await ctx.send(
                    "❓ **Missing Question**: Please include your question after the server selection.\nExample: `!ask [ServerName] What did PM say?`"
                )
                return

        # Find mutual servers with indexed data (regardless of configuration status)
        mutual_servers = await _get_mutual_servers_with_data(bot, ctx.author.id)

        if not mutual_servers:
            await ctx.send(
                "❌ **No Indexed Servers**: We don't share any servers with indexed messages. I need to be in servers with you to search their message history."
            )
            return

        # If server specified, find and validate it
        selected_server = None
        if server_selection:
            # Try to find by number first
            try:
                server_num = int(server_selection)
                if 1 <= server_num <= len(mutual_servers):
                    selected_server = mutual_servers[server_num - 1]
            except ValueError:
                # Try to find by name
                for server in mutual_servers:
                    if server.server_name.lower() == server_selection.lower():
                        selected_server = server
                        break

            if not selected_server:
                await ctx.send(
                    f"❌ **Invalid Server**: '{server_selection}' not found. Use `!ask` without server selection to see available options."
                )
                return

            # Check if the selected server is configured
            if not ConfigurationAgent.is_server_configured(selected_server.server_id):
                await ctx.send(
                    f"❌ **Server Not Configured**: '{selected_server.server_name}' hasn't been configured yet. Please ask the server admin to run the bot setup."
                )
                return

        # If server was specified and validated, proceed with the query
        if selected_server:
            success = await queue.add_request(
                user_id=user_id,
                server_id=selected_server.server_id,
                message=actual_message,
                discord_message_id=ctx.message.id,
                discord_channel=ctx.channel,
            )

            if success:
                position = queue.get_queue_position(user_id)
                server_name = selected_server.server_name
                if position == 1:
                    status_msg = await ctx.send(
                        f"⏳ **Queued**: Searching **{server_name}** - processing soon..."
                    )
                else:
                    status_msg = await ctx.send(
                        f"⏳ **Queued**: Position {position} in queue - will search **{server_name}**"
                    )

                # Store status message ID for updates
                if user_id in queue._active_requests:
                    queue._active_requests[user_id].status_message_id = status_msg.id
            else:
                await ctx.send(
                    "❌ **Queue Full**: Too many requests right now. Please try again in a few minutes."
                )
            return

        # No server specified - always show selection interface
        if len(mutual_servers) == 1:
            selection_text = "🔍 **Server Selection**: Which server should I search?\n\n"
        else:
            selection_text = "🔍 **Server Selection**: I found your question, but we're in multiple servers. Which server should I search?\n\n"

        # Import ConfigurationAgent for status checking
        for i, server in enumerate(mutual_servers, 1):
            last_indexed = (
                server.last_indexed.strftime("%Y-%m-%d")
                if server.last_indexed
                else "Never"
            )

            # Check configuration status
            is_configured = ConfigurationAgent.is_server_configured(server.server_id)
            config_status = "✅ Configured" if is_configured else "❌ Not Configured"

            selection_text += f"**{i}. {server.server_name}** ({config_status})\n"
            selection_text += f"   📊 {server.message_count:,} messages | 📅 Last indexed: {last_indexed}\n\n"

        selection_text += "**To proceed**, use `!ask` again but specify the server:\n"
        selection_text += (
            f"Example: `!ask [{mutual_servers[0].server_name}] {actual_message}`\n\n"
        )
        selection_text += "Or use server number: `!ask [1] {actual_message}`\n\n"
        selection_text += "⚠️ **Note**: Only configured servers can be searched. Ask the server admin to run bot setup for unconfigured servers."

        await ctx.send(selection_text)

    @bot.command(name="clear-conversation-history")
    async def clear_history_command(ctx: commands.Context) -> None:
        """Clear conversation history for the current user."""
        # Only work in DMs
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(
                "🔒 **DM Only**: This command only works in direct messages."
            )
            return

        conv_db = get_conversation_db()
        user_id = str(ctx.author.id)
        server_id = "0"  # DM context

        # Clear conversation history
        success = conv_db.clear_user_conversation_history(user_id, server_id)

        if success:
            await ctx.send(
                "🗑️ **History Cleared**: Your conversation history has been deleted."
            )
        else:
            await ctx.send(
                "❌ **Error**: Could not clear conversation history. Please try again."
            )

    @bot.command(name="help")
    async def help_command(ctx: commands.Context) -> None:
        """Show available bot commands and information."""
        embed = discord.Embed(
            title="🤖 Discord Indexer Bot",
            description="I index messages from server channels to enable AI-powered search and conversation.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 Available Commands",
            value=(
                "`!help` - Show this help message\n"
                "`!status` - Show bot status and statistics\n"
                "`!info` - Show detailed bot information"
            ),
            inline=False,
        )
        embed.add_field(
            name="🤖 DMAssistant Commands (DM Only)",
            value=(
                "`!ask <question>` - Ask me anything about your servers\n"
                "`!clear-conversation-history` - Delete your conversation history"
            ),
            inline=False,
        )
        embed.add_field(
            name="💬 How Questions Work",
            value=(
                "• Each `!ask` command is processed independently\n"
                "• Fair queue system - everyone gets equal access\n"
                "• Conversation history preserved for context\n"
                "• Multiple servers: use `!ask [ServerName] question`\n"
                "• I can search and reference server message history"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔒 Privacy Notice",
            value="Only server messages are indexed. DMs are private and never stored.",
            inline=False,
        )
        embed.set_footer(text="Start a conversation in DMs or use commands anywhere")

        await ctx.send(embed=embed)

    @bot.command(name="status")
    async def status_command(ctx: commands.Context) -> None:
        """Show current bot status and statistics."""
        guild_count = len(bot.guilds)
        channel_count = len(bot.get_all_channels())
        pipeline_status = "✅ Active" if bot.message_pipeline else "❌ Inactive"

        # Get queue statistics (session manager removed in Phase 1)
        queue = get_conversation_queue()
        queue_stats = queue.get_stats()

        embed = discord.Embed(title="📊 Bot Status", color=discord.Color.green())

        # Basic bot info
        embed.add_field(name="Servers", value=str(guild_count), inline=True)
        embed.add_field(name="Channels", value=str(channel_count), inline=True)
        embed.add_field(name="Pipeline", value=pipeline_status, inline=True)

        # DMAssistant stats (stateless queue-based processing)
        embed.add_field(
            name="Queue Size", value=str(queue_stats["queue_size"]), inline=True
        )
        embed.add_field(
            name="Total Processed",
            value=str(queue_stats["total_processed"]),
            inline=True,
        )
        embed.add_field(name="Processing Model", value="Stateless Queue", inline=True)

        # Memory stats
        embed.add_field(
            name="Processed Channels",
            value=str(len(bot.processed_channels)),
            inline=True,
        )
        embed.add_field(
            name="Messages in Memory", value=str(len(bot.stored_messages)), inline=True
        )
        embed.add_field(
            name="Queue Failed", value=str(queue_stats["total_failed"]), inline=True
        )

        embed.set_footer(
            text=f"Latency: {round(bot.latency * 1000)}ms | Processing: Stateless Queue"
        )

        await ctx.send(embed=embed)

    @bot.command(name="info")
    async def info_command(ctx: commands.Context) -> None:
        """Show detailed information about the bot."""
        embed = discord.Embed(
            title="ℹ️ About Discord Indexer Bot",
            description="Advanced Discord message indexing system for AI-powered search and analysis.",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="🎯 Purpose",
            value="Build searchable indexes of Discord server messages",
            inline=False,
        )
        embed.add_field(
            name="🔄 Message Flow",
            value=(
                "• **Server messages** → Indexed and searchable\n"
                "• **DM messages** → Private, never indexed\n"
                "• **Commands** → Processed instantly"
            ),
            inline=False,
        )
        embed.add_field(
            name="🧠 Technology",
            value="Powered by advanced NLP and vector embeddings",
            inline=False,
        )
        embed.set_footer(text="Developed for intelligent Discord data analysis")

        await ctx.send(embed=embed)

    # ===== COMMAND ERROR HANDLING =====
    @bot.event
    async def on_command_error(
        ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handle command errors gracefully."""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                f"❓ **Command not found!**\nUse `!help` to see available commands."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ **Missing required argument!**\n"
                f"Use `!help` for command usage information."
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"❌ **Invalid argument!**\nUse `!help` for command usage information."
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
