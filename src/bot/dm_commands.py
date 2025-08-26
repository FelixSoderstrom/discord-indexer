import discord
import asyncio
import logging
from typing import TYPE_CHECKING

from .voice_manager import (
    is_voice_session_active, 
    get_current_session_user_id,
    create_voice_session,
    cleanup_voice_session
)

if TYPE_CHECKING:
    from .client import DiscordBot


async def handle_dm_message(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle direct messages to the bot.
    
    Parses commands and routes them to appropriate handlers.
    DM messages never go through the indexing pipeline.
    
    Args:
        bot: DiscordBot instance
        message: DM message object to process
    """
    logger = logging.getLogger(__name__)
    
    # Only process messages that start with command prefix
    if not message.content.startswith("!"):
        return
    
    command = message.content.strip().lower()
    logger.info(f"🔧 DM command received from {message.author.name}: {command}")
    
    try:
        if command == "!join":
            await handle_join_command(bot, message)
        elif command == "!leave":
            await handle_leave_command(bot, message)
        else:
            await message.channel.send("Unknown command. Available commands: `!join`, `!leave`")
            
    except discord.Forbidden as e:
        logger.error(f"Permission denied handling DM command '{command}' from {message.author.name}: {e}")
        await message.channel.send("Sorry, I don't have permission to process that command.")
    except discord.HTTPException as e:
        logger.error(f"HTTP error handling DM command '{command}' from {message.author.name}: {e}")
        await message.channel.send("Sorry, there was a network error. Please try again.")
    except asyncio.TimeoutError as e:
        logger.error(f"Timeout handling DM command '{command}' from {message.author.name}: {e}")
        await message.channel.send("Sorry, the command timed out. Please try again.")
    except ValueError as e:
        logger.error(f"Invalid input for DM command '{command}' from {message.author.name}: {e}")
        await message.channel.send("Sorry, invalid input provided. Please check your command.")


async def handle_join_command(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle !join command from DM.
    
    Creates a private voice channel and joins with the user.
    Enforces single-session limitation.
    
    Args:
        bot: DiscordBot instance
        message: DM message containing !join command
    """
    logger = logging.getLogger(__name__)
    
    # Check if bot is already in a voice session
    if is_voice_session_active():
        await message.channel.send("🔒 I'm currently busy in another voice session. Please try again later.")
        return
    
    # Get user's available guilds
    user_guilds = [guild for guild in bot.guilds if guild.get_member(message.author.id)]
    
    if not user_guilds:
        await message.channel.send("❌ You're not in any servers that I have access to.")
        return
    
    if len(user_guilds) == 1:
        # Only one guild available, use it directly
        guild = user_guilds[0]
        await create_voice_session(bot, message, guild)
    else:
        # Multiple guilds available, ask user to choose
        guild_list = "\n".join([f"{i+1}. {guild.name}" for i, guild in enumerate(user_guilds)])
        await message.channel.send(
            f"Please choose a server:\n{guild_list}\n\n"
            f"Reply with the number (1-{len(user_guilds)}) of the server you'd like to use."
        )
        
        # Wait for user's guild selection
        def check(m):
            return (m.author == message.author and 
                    m.channel == message.channel and 
                    m.content.isdigit() and 
                    1 <= int(m.content) <= len(user_guilds))
        
        try:
            selection_msg = await bot.wait_for('message', check=check, timeout=30.0)
            selected_guild = user_guilds[int(selection_msg.content) - 1]
            await create_voice_session(bot, message, selected_guild)
        except asyncio.TimeoutError:
            await message.channel.send("⏰ Server selection timed out. Please try `!join` again.")


async def handle_leave_command(bot: "DiscordBot", message: discord.Message) -> None:
    """Handle !leave command from DM.
    
    Only allows the user currently in a voice session to leave.
    
    Args:
        bot: DiscordBot instance
        message: DM message containing !leave command
    """
    logger = logging.getLogger(__name__)
    
    if not is_voice_session_active():
        await message.channel.send("❌ There's no active voice session.")
        return
    
    current_user_id = get_current_session_user_id()
    if current_user_id != message.author.id:
        await message.channel.send("❌ You're not in the current voice session.")
        return
    
    await cleanup_voice_session(bot, "User requested leave")
    await message.channel.send("👋 Left the voice channel and cleaned up the session.")
