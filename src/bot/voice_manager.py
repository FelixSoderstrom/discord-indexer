import discord
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .client import DiscordBot


@dataclass
class VoiceSession:
    """Represents an active voice session between user and bot."""
    user_id: int
    user_name: str
    guild_id: int
    voice_channel_id: int
    created_at: datetime
    timeout_task: Optional[asyncio.Task] = None


# Global voice session management
current_voice_session: Optional[VoiceSession] = None
AFK_TIMEOUT_MINUTES = 5


def is_voice_session_active() -> bool:
    """Check if there's an active voice session.
    
    Returns:
        True if bot is currently in a voice session, False otherwise
    """
    return current_voice_session is not None


def get_current_session_user_id() -> Optional[int]:
    """Get the user ID of the current voice session.
    
    Returns:
        User ID if session exists, None otherwise
    """
    return current_voice_session.user_id if current_voice_session else None


async def create_voice_session(bot: "DiscordBot", message: discord.Message, guild: discord.Guild) -> None:
    """Create a private voice channel and establish voice session.
    
    Validates permissions, creates channel with restricted access, and joins.
    
    Args:
        bot: DiscordBot instance
        message: Original DM message
        guild: Guild to create voice channel in
    """
    global current_voice_session
    logger = logging.getLogger(__name__)
    
    try:
        # LBYL: Check bot permissions
        if not guild.me.guild_permissions.manage_channels:
            await message.channel.send(f"❌ I don't have permission to manage channels in {guild.name}.")
            return
        
        if not guild.me.guild_permissions.connect:
            await message.channel.send(f"❌ I don't have permission to connect to voice channels in {guild.name}.")
            return
        
        # Create private voice channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
            guild.me: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True),
            message.author: discord.PermissionOverwrite(connect=True, speak=True, view_channel=True)
        }
        
        channel_name = f"Private - {message.author.display_name}"
        voice_channel = await guild.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            reason="Private voice session with bot"
        )
        
        logger.info(f"Created voice channel '{channel_name}' in {guild.name}")
        
        # Join the voice channel
        voice_client = await voice_channel.connect()
        logger.info(f"Bot joined voice channel '{channel_name}'")
        
        # Create voice session
        current_voice_session = VoiceSession(
            user_id=message.author.id,
            user_name=message.author.display_name,
            guild_id=guild.id,
            voice_channel_id=voice_channel.id,
            created_at=datetime.now()
        )
        
        # Start AFK timeout
        current_voice_session.timeout_task = asyncio.create_task(
            afk_timeout_handler(bot, AFK_TIMEOUT_MINUTES * 60)
        )
        
        await message.channel.send(
            f"✅ Created private voice channel in **{guild.name}**!\n"
            f"🎤 Join the channel: **{channel_name}**\n"
            f"⏰ Session will auto-close after {AFK_TIMEOUT_MINUTES} minutes of inactivity."
        )
        
    except discord.Forbidden as e:
        logger.error(f"Permission denied creating voice channel in {guild.name}: {e}")
        await message.channel.send(f"❌ Permission denied. I need 'Manage Channels' and 'Connect' permissions in {guild.name}.")
    except discord.HTTPException as e:
        logger.error(f"HTTP error creating voice channel in {guild.name}: {e}")
        await message.channel.send(f"❌ Failed to create voice channel in {guild.name}. Please try again.")
    except asyncio.TimeoutError as e:
        logger.error(f"Timeout connecting to voice channel in {guild.name}: {e}")
        await message.channel.send(f"❌ Timeout connecting to voice channel in {guild.name}. Please try again.")
    except discord.ClientException as e:
        logger.error(f"Client error during voice session creation in {guild.name}: {e}")
        await message.channel.send(f"❌ Bot is already connected to a voice channel. Please try again.")
    except RuntimeError as e:
        logger.error(f"Runtime error during voice session creation in {guild.name}: {e}")
        if "PyNaCl" in str(e):
            await message.channel.send("❌ Voice functionality requires PyNaCl library. Please contact the bot administrator.")
        else:
            await message.channel.send(f"❌ Runtime error: {e}")


async def cleanup_voice_session(bot: "DiscordBot", reason: str = "Session cleanup") -> None:
    """Clean up current voice session.
    
    Leaves voice channel, deletes it, and resets session state.
    
    Args:
        bot: DiscordBot instance
        reason: Reason for cleanup (for logging)
    """
    global current_voice_session
    logger = logging.getLogger(__name__)
    
    if current_voice_session is None:
        return
    
    logger.info(f"Cleaning up voice session: {reason}")
    
    try:
        # Cancel timeout task
        if current_voice_session.timeout_task and not current_voice_session.timeout_task.done():
            current_voice_session.timeout_task.cancel()
        
        # Get guild and channel
        guild = bot.get_guild(current_voice_session.guild_id)
        if guild:
            voice_channel = guild.get_channel(current_voice_session.voice_channel_id)
            
            # Leave voice channel if connected
            voice_client = guild.voice_client
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
                logger.info("Bot disconnected from voice channel")
            
            # Delete voice channel
            if voice_channel:
                await voice_channel.delete(reason=f"Voice session cleanup: {reason}")
                logger.info(f"Deleted voice channel '{voice_channel.name}'")
        
    except discord.Forbidden as e:
        logger.error(f"Permission denied during voice session cleanup: {e}")
    except discord.HTTPException as e:
        logger.error(f"HTTP error during voice session cleanup: {e}")
    except discord.NotFound as e:
        logger.warning(f"Voice channel or guild not found during cleanup: {e}")
    except discord.ClientException as e:
        logger.error(f"Client error during voice session cleanup: {e}")
    finally:
        current_voice_session = None
        logger.info("Voice session state reset")


async def afk_timeout_handler(bot: "DiscordBot", timeout_seconds: int) -> None:
    """Handle AFK timeout for voice sessions.
    
    Args:
        bot: DiscordBot instance
        timeout_seconds: Timeout duration in seconds
    """
    global current_voice_session
    logger = logging.getLogger(__name__)
    
    try:
        await asyncio.sleep(timeout_seconds)
        
        if current_voice_session is not None:
            logger.info(f"Voice session timed out after {timeout_seconds}s")
            
            # Try to notify user
            try:
                user = bot.get_user(current_voice_session.user_id)
                if user:
                    await user.send(f"⏰ Voice session timed out after {AFK_TIMEOUT_MINUTES} minutes of inactivity.")
            except discord.Forbidden as e:
                logger.warning(f"Could not DM user for timeout notification (blocked DMs): {e}")
            except discord.HTTPException as e:
                logger.warning(f"HTTP error sending timeout notification: {e}")
            except discord.NotFound as e:
                logger.warning(f"User not found for timeout notification: {e}")
            
            await cleanup_voice_session(bot, "AFK timeout")
            
    except asyncio.CancelledError:
        # Timeout was cancelled (normal cleanup)
        pass
    except discord.Forbidden as e:
        logger.error(f"Permission denied in AFK timeout handler: {e}")
    except discord.HTTPException as e:
        logger.error(f"HTTP error in AFK timeout handler: {e}")
    except discord.NotFound as e:
        logger.warning(f"User not found for timeout notification: {e}")
    except OSError as e:
        logger.error(f"Network error in AFK timeout handler: {e}")


async def handle_voice_state_update(
    bot: "DiscordBot", 
    member: discord.Member, 
    before: discord.VoiceState, 
    after: discord.VoiceState
) -> None:
    """Handle voice state updates for automatic session cleanup.
    
    Monitors when users leave voice channels to trigger cleanup.
    
    Args:
        bot: DiscordBot instance
        member: Member whose voice state changed
        before: Voice state before the change
        after: Voice state after the change
    """
    global current_voice_session
    logger = logging.getLogger(__name__)
    
    if current_voice_session is None:
        return
    
    # Check if the user in our voice session left a voice channel
    if (member.id == current_voice_session.user_id and 
        before.channel is not None and 
        after.channel is None):
        
        logger.info(f"User {member.display_name} left voice channel, cleaning up session")
        await cleanup_voice_session(bot, "User left voice channel")
        
        # Notify user
        try:
            await member.send("👋 You left the voice channel. Session has been cleaned up.")
        except discord.Forbidden as e:
            logger.warning(f"Could not DM user for cleanup notification (blocked DMs): {e}")
        except discord.HTTPException as e:
            logger.warning(f"HTTP error sending cleanup notification: {e}")
        except discord.NotFound as e:
            logger.warning(f"User not found for cleanup notification: {e}")
    
    # Check if user moved away from our private channel
    elif (member.id == current_voice_session.user_id and 
          before.channel is not None and 
          before.channel.id == current_voice_session.voice_channel_id and
          after.channel is not None and 
          after.channel.id != current_voice_session.voice_channel_id):
        
        logger.info(f"User {member.display_name} moved away from private channel, cleaning up session")
        await cleanup_voice_session(bot, "User moved to different channel")
        
        # Notify user
        try:
            await member.send("👋 You moved to a different voice channel. Private session has been cleaned up.")
        except discord.Forbidden as e:
            logger.warning(f"Could not DM user for cleanup notification (blocked DMs): {e}")
        except discord.HTTPException as e:
            logger.warning(f"HTTP error sending cleanup notification: {e}")
        except discord.NotFound as e:
            logger.warning(f"User not found for cleanup notification: {e}")
