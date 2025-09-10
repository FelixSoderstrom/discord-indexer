import discord
from discord.ext import commands
import logging
import sys
from typing import TYPE_CHECKING
from typing import List
from ..llm.agents.session_manager import ServerOption
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
    
    # Initialize LangChain DMAssistant for conversation handling
    logger.info("🤖 Initializing LangChain DMAssistant...")
    try:
        from ..llm.agents.langchain_dm_assistant import LangChainDMAssistant
        bot.dm_assistant = LangChainDMAssistant()
        
        # Verify model is available and healthy
        if bot.dm_assistant.health_check():
            logger.info("✅ LangChain DMAssistant initialized successfully with model ready")
        else:
            logger.error("❌ LangChain DMAssistant model health check failed")
            raise RuntimeError("LangChain DMAssistant model not available")
        
        # Initialize session manager
        logger.info("🕒 Starting session manager...")
        from ..llm.agents.session_manager import initialize_session_manager
        session_manager = initialize_session_manager(timeout_minutes=5)
        await session_manager.start_cleanup_task()
        bot.session_manager = session_manager  # Store reference for cleanup
        logger.info("✅ Session manager started successfully")
        
        # Initialize queue worker with LangChain
        logger.info("⚡ Starting LangChain conversation queue worker...")
        from ..llm.agents.queue_worker import initialize_queue_worker
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
    
    If user has active session, message is sent to DMAssistant via queue.
    Otherwise, provides helpful guidance about available commands.
    
    Args:
        bot: DiscordBot instance
        message: Discord DM message object
    """
    logger = logging.getLogger(__name__)
    
    content_preview = message.content[:30] + "..." if len(message.content) > 30 else message.content
    logger.info(f"💬 Received non-command DM from {message.author.name}: {content_preview}")
    
    # Check if user has an active session
    from ..llm.agents.session_manager import get_session_manager
    from ..llm.agents.conversation_queue import get_conversation_queue
    
    session_manager = get_session_manager()
    queue = get_conversation_queue()
    user_id = str(message.author.id)
    
    # Check if user is waiting for server selection
    if session_manager.has_pending_server_selection(user_id):
        await _handle_server_selection_response(bot, message, session_manager, queue)
        return
    
    # If user has active session, process message via DMAssistant
    if session_manager.has_active_session(user_id):
        # Update session activity
        session_manager.update_session_activity(user_id)
        
        # Check if user already has a request queued
        if queue.is_user_queued(user_id):
            await message.channel.send("⏳ **Processing**: Please wait, I'm still working on your previous message.")
            return
        
        # Get server ID from active session
        session = session_manager.get_session(user_id)
        server_id = session.server_id if session else None
        
        if not server_id:
            await message.channel.send("❌ **Session Error**: Could not determine which server to search. Please use `!end` and start over with `!ask`.")
            return
        
        # Add message to queue for DMAssistant processing
        success = await queue.add_request(
            user_id=user_id,
            server_id=server_id,
            message=message.content,
            discord_message_id=message.id,
            discord_channel=message.channel
        )
        
        if success:
            await message.channel.send("🤖 **Processing**: I'm thinking about your message...")
        else:
            await message.channel.send("❌ **Queue Full**: I'm too busy right now. Please try again in a moment.")
        
        return
    
    # If no active session, provide helpful guidance
    await message.channel.send(
        "👋 Hello! I'm the Discord Indexer Bot.\n\n"
        "To start a conversation with me, use:\n"
        "• `!ask <your question>` - Start AI conversation\n"
        "• `!help` - Show all available commands\n"
        "• `!status` - Show bot status\n\n"
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
    
    # ===== HELPER FUNCTIONS =====
    
    async def _get_mutual_servers_with_data(bot: "DiscordBot", user_id: int) -> List[ServerOption]:
        """Get servers shared between bot and user, with indexing data.
        
        Args:
            bot: DiscordBot instance
            user_id: Discord user ID
            
        Returns:
            List of ServerOption objects with indexing information
        """
        from ..db.setup_db import get_db
        import os
        from datetime import datetime
        
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
                    db_path = os.path.join("src", "db", "databases", server_id, "chroma_data")
                    
                    if os.path.exists(db_path):
                        # Get ChromaDB client and check message count
                        client = get_db(int(server_id))
                        collection = client.get_or_create_collection(
                            name="messages",
                            metadata={"server_id": server_id}
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
                            last_indexed = datetime.fromtimestamp(os.path.getmtime(db_path))
                        
                        mutual_servers.append(ServerOption(
                            server_id=server_id,
                            server_name=server_name,
                            last_indexed=last_indexed,
                            message_count=message_count
                        ))
                        
                except Exception as e:
                    # Log error but continue - this server just won't be available
                    logger.warning(f"Error checking indexing data for server {server_id} ({server_name}): {e}")
                    continue
        
        # Sort by message count (most active servers first)
        mutual_servers.sort(key=lambda x: x.message_count, reverse=True)
        
        return mutual_servers
    
    async def _handle_server_selection_response(bot: "DiscordBot", message: discord.Message, session_manager, queue) -> None:
        """Handle user's server selection response.
        
        Args:
            bot: DiscordBot instance
            message: Discord message with server selection
            session_manager: SessionManager instance
            queue: ConversationQueue instance
        """
        user_id = str(message.author.id)
        selection_data = session_manager.get_pending_server_selection(user_id)
        
        if not selection_data:
            await message.channel.send("❌ **Selection Expired**: Your server selection has expired. Use `!ask` to start over.")
            return
        
        user_choice = message.content.strip()
        selected_server = None
        
        # Try to match by number first
        try:
            choice_num = int(user_choice)
            if 1 <= choice_num <= len(selection_data.available_servers):
                selected_server = selection_data.available_servers[choice_num - 1]
        except ValueError:
            # Not a number, try to match by server name
            for server in selection_data.available_servers:
                if user_choice.lower() == server.server_name.lower():
                    selected_server = server
                    break
        
        if not selected_server:
            # Invalid selection
            valid_options = []
            for i, server in enumerate(selection_data.available_servers, 1):
                valid_options.append(f"**{i}** or **{server.server_name}**")
            
            await message.channel.send(
                f"❓ **Invalid Selection**: '{user_choice}' is not a valid option.\n\n"
                f"Please choose: {', '.join(valid_options)}"
            )
            return
        
        # Valid server selected - remove from pending and create session
        session_manager.complete_server_selection(user_id)
        session_manager.create_session(user_id, selected_server.server_id, message.channel)
        
        # Add original question to queue
        success = await queue.add_request(
            user_id=user_id,
            server_id=selected_server.server_id,
            message=selection_data.original_question,
            discord_message_id=message.id,
            discord_channel=message.channel
        )
        
        if success:
            position = queue.get_queue_position(user_id)
            server_name = selected_server.server_name
            
            if position == 1:
                status_msg = await message.channel.send(f"✅ **Server Selected**: **{server_name}** - processing your question now...")
            else:
                status_msg = await message.channel.send(f"✅ **Server Selected**: **{server_name}** - position {position} in queue")
            
            # Store status message ID for updates
            if user_id in queue._active_requests:
                queue._active_requests[user_id].status_message_id = status_msg.id
        else:
            await message.channel.send(
                f"✅ **Server Selected**: **{selected_server.server_name}**\n"
                f"❌ **Queue Full**: Too many requests right now. Please try again in a few minutes."
            )
    
    # ===== COMMAND HANDLERS =====
    @bot.command(name='ask')
    async def ask_command(ctx: commands.Context, *, message: str = None) -> None:
        """Start a conversation with the DMAssistant."""
        if not message:
            await ctx.send("❓ **Usage**: `!ask <your question>`\nExample: `!ask What did PM say about the standup?`")
            return
        
        # Only work in DMs
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("🔒 **DM Only**: The `!ask` command only works in direct messages for privacy.")
            return
        
        # Import systems
        from ..llm.agents.conversation_queue import get_conversation_queue
        from ..llm.agents.session_manager import get_session_manager, ServerOption
        
        queue = get_conversation_queue()
        session_manager = get_session_manager()
        user_id = str(ctx.author.id)
        
        # Check if user already has a request queued
        if queue.is_user_queued(user_id):
            await ctx.send("⏳ **Already Processing**: You already have a conversation request in progress. Please wait for it to complete or use `!end` to cancel.")
            return
        
        # Check if user is already waiting for server selection
        if session_manager.has_pending_server_selection(user_id):
            await ctx.send("⏳ **Server Selection Pending**: You're already choosing a server. Please complete your selection or wait for timeout.")
            return
        
        # Find mutual servers
        mutual_servers = await _get_mutual_servers_with_data(bot, ctx.author.id)
        
        if not mutual_servers:
            await ctx.send("❌ **No Indexed Servers**: We don't share any servers with indexed messages. I need to be in servers with you to search their message history.")
            return
        
        # If only one server, go directly to queue
        if len(mutual_servers) == 1:
            server = mutual_servers[0]
            session_manager.create_session(user_id, server.server_id, ctx.channel)
            
            success = await queue.add_request(
                user_id=user_id,
                server_id=server.server_id,
                message=message,
                discord_message_id=ctx.message.id,
                discord_channel=ctx.channel
            )
            
            if success:
                position = queue.get_queue_position(user_id)
                server_name = server.server_name
                if position == 1:
                    status_msg = await ctx.send(f"⏳ **Queued**: Searching **{server_name}** - processing soon...")
                else:
                    status_msg = await ctx.send(f"⏳ **Queued**: Position {position} in queue - will search **{server_name}**")
                    
                # Store status message ID for updates
                if user_id in queue._active_requests:
                    queue._active_requests[user_id].status_message_id = status_msg.id
            else:
                await ctx.send("❌ **Queue Full**: Too many requests right now. Please try again in a few minutes.")
            return
        
        # Multiple servers - ask user to choose
        session_manager.add_pending_server_selection(
            user_id=user_id,
            question=message,
            servers=mutual_servers,
            discord_channel=ctx.channel
        )
        
        # Send server selection message
        selection_text = "🔍 **Server Selection**: I found your question, but we're in multiple servers. Which server should I search?\n\n"
        
        for i, server in enumerate(mutual_servers, 1):
            last_indexed = server.last_indexed.strftime('%Y-%m-%d') if server.last_indexed else "Never"
            selection_text += f"**{i}. {server.server_name}**\n"
            selection_text += f"   📊 {server.message_count:,} messages | 📅 Last indexed: {last_indexed}\n\n"
        
        selection_text += "Reply with the **server name** or **number** (e.g., '1' or 'ProjectTeam').\n"
        selection_text += "⏰ You have 5 minutes to respond."
        
        await ctx.send(selection_text)
    
    @bot.command(name='end')
    async def end_command(ctx: commands.Context) -> None:
        """End active conversation with DMAssistant."""
        # Only work in DMs
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("🔒 **DM Only**: The `!end` command only works in direct messages.")
            return
        
        from ..llm.agents.conversation_queue import get_conversation_queue
        from ..llm.agents.session_manager import get_session_manager
        
        queue = get_conversation_queue()
        session_manager = get_session_manager()
        user_id = str(ctx.author.id)
        
        # End session and check if user had active request
        session_ended = session_manager.end_session(user_id)
        queue_cancelled = queue.is_user_queued(user_id)
        
        if session_ended or queue_cancelled:
            await ctx.send("✅ **Session Ended**: Your conversation has been ended.")
        else:
            await ctx.send("❓ **No Active Session**: You don't have an active conversation to end.")
    
    @bot.command(name='clear-conversation-history')
    async def clear_history_command(ctx: commands.Context) -> None:
        """Clear conversation history for the current user."""
        # Only work in DMs
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("🔒 **DM Only**: This command only works in direct messages.")
            return
        
        from ..db.conversation_db import get_conversation_db
        
        conv_db = get_conversation_db()
        user_id = str(ctx.author.id)
        server_id = "0"  # DM context
        
        # Clear conversation history
        success = conv_db.clear_user_conversation_history(user_id, server_id)
        
        if success:
            await ctx.send("🗑️ **History Cleared**: Your conversation history has been deleted.")
        else:
            await ctx.send("❌ **Error**: Could not clear conversation history. Please try again.")
    
    @bot.command(name='help')
    async def help_command(ctx: commands.Context) -> None:
        """Show available bot commands and information."""
        embed = discord.Embed(
            title="🤖 Discord Indexer Bot",
            description="I index messages from server channels to enable AI-powered search and conversation.",
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
            name="🤖 DMAssistant Commands (DM Only)",
            value=(
                "`!ask <question>` - Start AI conversation session\n"
                "`!end` - End active conversation session\n"
                "`!clear-conversation-history` - Delete your conversation history"
            ),
            inline=False
        )
        embed.add_field(
            name="💬 How Conversations Work",
            value=(
                "• Start with `!ask <question>` in DMs\n"
                "• Continue chatting naturally (no commands needed)\n"
                "• Sessions auto-expire after 5 minutes of inactivity\n"
                "• I can search and reference server message history"
            ),
            inline=False
        )
        embed.add_field(
            name="🔒 Privacy Notice",
            value="Only server messages are indexed. DMs are private and never stored.",
            inline=False
        )
        embed.set_footer(text="Start a conversation in DMs or use commands anywhere")
        
        await ctx.send(embed=embed)
    
    @bot.command(name='status')
    async def status_command(ctx: commands.Context) -> None:
        """Show current bot status and statistics."""
        guild_count = len(bot.guilds)
        channel_count = len(bot.get_all_channels())
        pipeline_status = "✅ Active" if bot.message_pipeline else "❌ Inactive"
        
        # Get session and queue statistics
        from ..llm.agents.session_manager import get_session_manager
        from ..llm.agents.conversation_queue import get_conversation_queue
        
        session_manager = get_session_manager()
        queue = get_conversation_queue()
        
        session_stats = session_manager.get_session_stats()
        queue_stats = queue.get_stats()
        
        embed = discord.Embed(
            title="📊 Bot Status",
            color=discord.Color.green()
        )
        
        # Basic bot info
        embed.add_field(name="Servers", value=str(guild_count), inline=True)
        embed.add_field(name="Channels", value=str(channel_count), inline=True)
        embed.add_field(name="Pipeline", value=pipeline_status, inline=True)
        
        # DMAssistant stats
        embed.add_field(name="Active Sessions", value=str(session_stats["active_sessions"]), inline=True)
        embed.add_field(name="Queue Size", value=str(queue_stats["queue_size"]), inline=True)
        embed.add_field(name="Total Processed", value=str(queue_stats["total_processed"]), inline=True)
        
        # Memory stats
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
        embed.add_field(name="Queue Failed", value=str(queue_stats["total_failed"]), inline=True)
        
        embed.set_footer(text=f"Latency: {round(bot.latency * 1000)}ms | Session Timeout: {session_stats['timeout_minutes']}min")
        
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
