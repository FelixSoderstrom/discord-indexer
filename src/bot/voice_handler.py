"""Voice channel management for Discord bot.

Handles voice channel creation, permissions, lifecycle management,
and cleanup for voice-based user interactions.
"""

import asyncio
import logging
from typing import Dict, Optional, List

import discord

from src.db.conversation_db import get_conversation_db
from src.config.settings import settings


logger = logging.getLogger(__name__)

# Global singleton instance
_voice_manager: Optional['VoiceChannelManager'] = None


class VoiceChannelManager:
    """Manages voice channel lifecycle and bot voice connections."""

    def __init__(self, bot):
        """Initialize voice channel manager.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.db = get_conversation_db()
        self.active_timers: Dict[int, asyncio.Task] = {}  # channel_id -> timer task
        self.channels_pending_deletion: List[int] = []  # List of channel IDs awaiting deletion

    async def create_private_channel(
        self,
        guild: discord.Guild,
        user: discord.Member
    ) -> discord.VoiceChannel:
        """Create a private voice channel for a user.

        Args:
            guild: Discord guild to create channel in
            user: User who will have access to the channel

        Returns:
            Created voice channel

        Raises:
            discord.HTTPException: If channel creation fails
        """
        # Define permissions: user can view/connect, @everyone cannot
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
                connect=False
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True
            )
        }

        # Create channel with user's name
        channel_name = f"voice-{user.name}"
        channel = await guild.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Private voice channel for {user.name}"
        )

        # Add channel to pending deletion list
        # DEBUG: Log queue state before adding
        logger.debug(f"DEBUG: Deletion queue BEFORE adding {channel.id}: {self.channels_pending_deletion}")
        self.channels_pending_deletion.append(channel.id)
        # DEBUG: Log queue state after adding
        logger.debug(f"DEBUG: Deletion queue AFTER adding {channel.id}: {self.channels_pending_deletion}")

        logger.info(
            f"Created private voice channel '{channel_name}' "
            f"(ID: {channel.id}) in guild '{guild.name}'"
        )
        return channel

    async def join_channel(
        self,
        channel: discord.VoiceChannel
    ) -> discord.VoiceClient:
        """Bot joins a voice channel.

        Args:
            channel: Voice channel to join

        Returns:
            Voice client connection

        Raises:
            discord.ClientException: If already connected to voice in this guild
        """
        voice_client = await channel.connect()
        logger.info(f"Bot joined voice channel '{channel.name}' (ID: {channel.id})")
        return voice_client

    async def start_alone_timer(
        self,
        channel_id: int,
        user_id: str,
        session_id: int
    ) -> None:
        """Start timer to cleanup channel if user doesn't join within timeout.

        Args:
            channel_id: Voice channel ID
            user_id: Expected user ID
            session_id: Database session ID
        """
        timeout = settings.VOICE_TIMEOUT

        async def timer_task():
            """Timer task that checks if user joined after timeout."""
            try:
                await asyncio.sleep(timeout)

                # Get channel
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    logger.warning(
                        f"Channel {channel_id} not found after timeout, "
                        "assuming already cleaned up"
                    )
                    return

                # Check if user is in channel
                user_in_channel = any(
                    str(member.id) == user_id
                    for member in channel.members
                )

                if not user_in_channel:
                    logger.info(
                        f"User {user_id} did not join channel {channel_id} "
                        f"within {timeout}s, triggering cleanup"
                    )
                    # DEBUG: Log that user is NOT in channel
                    logger.debug(f"DEBUG: User {user_id} NOT in channel {channel_id} - proceeding with cleanup")

                    # Use the database to ensure we have the right channel to cleanup
                    logger.debug(f"DEBUG: Looking up session for channel {channel_id}")
                    session = self.db.get_active_session_by_channel(str(channel_id))

                    # DEBUG: Log session lookup result with full details
                    logger.debug(f"DEBUG: Session lookup result: {session}")

                    if session:
                        # DEBUG: Log before calling cleanup_channel
                        logger.debug(
                            f"DEBUG: Calling cleanup_channel for session - "
                            f"channel_id={session['channel_id']}, session_id={session['id']}, "
                            f"user_id={session.get('user_id')}, guild_id={session.get('guild_id')}"
                        )
                        await self.cleanup_channel(int(session['channel_id']), session['id'])
                    else:
                        logger.warning(f"No active session found for channel {channel_id}")
                else:
                    logger.debug(
                        f"User {user_id} is in channel {channel_id}, "
                        "timer completed without cleanup"
                    )

            except asyncio.CancelledError:
                logger.debug(f"Timer cancelled for channel {channel_id}")
                raise
            except discord.HTTPException as e:
                logger.error(f"Discord error in timer for channel {channel_id}: {e}", exc_info=True)
            except Exception as e:
                # DEBUG: Catch ANY unhandled exception with full traceback
                logger.error(
                    f"DEBUG: UNHANDLED EXCEPTION in timer_task for channel {channel_id}: {type(e).__name__}: {e}",
                    exc_info=True
                )
            finally:
                # Remove from active timers
                if channel_id in self.active_timers:
                    del self.active_timers[channel_id]

        # Create and store timer task
        task = asyncio.create_task(timer_task())
        self.active_timers[channel_id] = task

        logger.debug(
            f"Started {timeout}s alone timer for channel {channel_id}, "
            f"user {user_id}"
        )

    def cancel_timer(self, channel_id: int) -> None:
        """Cancel active timer for a channel.

        Args:
            channel_id: Voice channel ID
        """
        if channel_id in self.active_timers:
            task = self.active_timers[channel_id]
            task.cancel()
            logger.debug(f"Cancelled timer for channel {channel_id}")

    async def cleanup_channel(
        self,
        channel_id: int,
        session_id: int,
        free_queue_slot: bool = True
    ) -> None:
        """Cleanup voice channel and end session.

        Args:
            channel_id: Voice channel ID to cleanup
            session_id: Database session ID
            free_queue_slot: Whether to free the queue slot
        """
        # DEBUG: Log that cleanup_channel was actually called
        logger.info(
            f"DEBUG: cleanup_channel CALLED with channel_id={channel_id}, "
            f"session_id={session_id}, free_queue_slot={free_queue_slot}"
        )
        logger.debug(f"DEBUG: Current channels_pending_deletion: {self.channels_pending_deletion}")

        # CRITICAL: Retrieve session data BEFORE any operations that might invalidate it
        session = self.db.get_active_session_by_channel(str(channel_id))

        if not session:
            logger.warning(
                f"No active session found for channel {channel_id} "
                f"(session_id: {session_id}). Channel may already be cleaned up."
            )
            # Still try to clean up what we can
            session = {'guild_id': None, 'user_id': None}
        else:
            logger.debug(
                f"Starting cleanup for channel {channel_id}, session {session_id}, "
                f"user {session['user_id']}, guild {session['guild_id']}"
            )

        # Store essential session data before any operations
        guild_id = int(session['guild_id']) if session.get('guild_id') else None
        user_id = session.get('user_id')

        try:
            # Step 1: Cancel any active timer
            self.cancel_timer(channel_id)

            # Step 2: Disconnect bot from voice (before we lose channel reference)
            voice_client = None
            for vc in self.bot.voice_clients:
                if vc.channel and vc.channel.id == channel_id:
                    voice_client = vc
                    break

            if voice_client and voice_client.is_connected():
                try:
                    # DEBUG: Log before disconnect
                    logger.debug(f"DEBUG: About to disconnect bot from channel {channel_id}")
                    await voice_client.disconnect(force=False)
                    # DEBUG: Log after successful disconnect
                    logger.info(f"DEBUG: Bot disconnected successfully from voice channel {channel_id}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to disconnect from channel {channel_id}: {e}", exc_info=True)

            # Step 3: Delete ALL pending channels (brute-force approach to ensure cleanup)
            logger.info(
                f"Processing deletion queue: {len(self.channels_pending_deletion)} "
                f"channels pending deletion: {self.channels_pending_deletion}"
            )

            # DEBUG: Log before entering loop
            logger.debug(
                f"DEBUG: About to process deletion queue with {len(self.channels_pending_deletion)} channels"
            )

            successfully_deleted = []

            for pending_channel_id in list(self.channels_pending_deletion):
                # DEBUG: Log for each channel in loop
                logger.debug(f"DEBUG: Attempting to delete channel {pending_channel_id} from deletion queue")

                # Try to get guild_id for this channel from database
                pending_session = self.db.get_active_session_by_channel(str(pending_channel_id))
                pending_guild_id = None

                if pending_session and pending_session.get('guild_id'):
                    pending_guild_id = int(pending_session['guild_id'])
                elif pending_channel_id == channel_id and guild_id:
                    # Use the guild_id we already have for current channel
                    pending_guild_id = guild_id

                # Attempt deletion
                deleted = False
                if pending_guild_id:
                    deleted = await self.ensure_channel_deleted(pending_channel_id, pending_guild_id)
                else:
                    # Fallback: try direct deletion from cache
                    pending_channel = self.bot.get_channel(pending_channel_id)
                    if pending_channel:
                        try:
                            await pending_channel.delete(reason="Voice session cleanup")
                            logger.info(f"Deleted channel {pending_channel_id} (fallback method)")
                            deleted = True
                        except discord.HTTPException as e:
                            logger.error(f"Failed to delete channel {pending_channel_id}: {e}")
                        except discord.NotFound:
                            # Channel already deleted
                            logger.info(f"Channel {pending_channel_id} already deleted")
                            deleted = True
                    else:
                        logger.warning(
                            f"Could not delete channel {pending_channel_id} - "
                            "no guild_id and channel not in cache"
                        )

                # Track successful deletions for removal from queue
                if deleted:
                    successfully_deleted.append(pending_channel_id)
                    logger.info(f"DEBUG: Successfully deleted channel {pending_channel_id}")
                else:
                    logger.warning(f"DEBUG: Failed to delete channel {pending_channel_id}")

            # Remove successfully deleted channels from pending list
            for deleted_id in successfully_deleted:
                if deleted_id in self.channels_pending_deletion:
                    # DEBUG: Log what is being removed
                    logger.debug(f"DEBUG: Removing channel {deleted_id} from deletion queue")
                    self.channels_pending_deletion.remove(deleted_id)
                    logger.debug(f"DEBUG: Channel {deleted_id} removed. Queue now: {self.channels_pending_deletion}")

            logger.info(
                f"Deletion queue processed: {len(successfully_deleted)} channels deleted, "
                f"{len(self.channels_pending_deletion)} still pending: {self.channels_pending_deletion}"
            )

            # Step 4: Free queue slot BEFORE ending session (so we can still find user_id)
            if free_queue_slot and user_id:
                try:
                    from src.ai.agents.conversation_queue import get_conversation_queue

                    queue = get_conversation_queue()
                    if user_id in queue._active_requests:
                        request = queue._active_requests[user_id]
                        await queue.complete_request(request, success=True)
                        logger.info(f"Freed queue slot for user {user_id}")
                    else:
                        logger.debug(f"No active queue request found for user {user_id}")
                except ImportError as e:
                    logger.error(f"Failed to import conversation queue: {e}")
                except AttributeError as e:
                    logger.error(f"Queue attribute error for user {user_id}: {e}")
                except KeyError as e:
                    logger.error(f"Queue key error for user {user_id}: {e}")

            # Step 5: End database session (LAST step - after all operations complete)
            success = self.db.end_voice_session(session_id)
            if success:
                logger.info(f"Ended voice session {session_id}")
            else:
                logger.warning(f"Failed to end voice session {session_id} in database")

        except discord.HTTPException as e:
            logger.error(f"Discord error cleaning up channel {channel_id}: {e}")
            # Still try to end the session
            self.db.end_voice_session(session_id)
        except discord.NotFound as e:
            logger.warning(f"Channel {channel_id} not found during cleanup: {e}")
            # Channel already deleted, end the session
            self.db.end_voice_session(session_id)
        except discord.Forbidden as e:
            logger.error(f"Permission error cleaning up channel {channel_id}: {e}")
            # Still end the session even if we can't delete the channel
            self.db.end_voice_session(session_id)

    async def ensure_channel_deleted(self, channel_id: int, guild_id: int) -> bool:
        """Ensure a voice channel is deleted using all available methods.

        Args:
            channel_id: Voice channel ID to delete
            guild_id: Guild ID where channel exists

        Returns:
            True if channel was deleted or doesn't exist, False if deletion failed
        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Guild {guild_id} not found")
            return False

        # Method 1: Try to get from cache
        channel = guild.get_channel(channel_id)

        # Method 2: If not in cache, fetch from API
        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.NotFound:
                # Channel doesn't exist, that's fine
                logger.info(f"Channel {channel_id} already deleted or doesn't exist")
                return True
            except discord.HTTPException as e:
                logger.error(f"Failed to fetch channel {channel_id}: {e}")
                return False

        # Delete the channel
        if channel:
            try:
                await channel.delete(reason="Voice session cleanup")
                logger.info(f"Successfully deleted channel {channel_id}")
                return True
            except discord.HTTPException as e:
                logger.error(f"Failed to delete channel {channel_id}: {e}")
                return False

        return True

    async def cleanup_all_voice_channels(self) -> None:
        """Cleanup all active voice channels using stored session data.

        Used during shutdown and for forced cleanup.
        Also processes the entire deletion queue to ensure no orphaned channels remain.
        """
        active_sessions = self.db.get_all_active_sessions()

        logger.info(f"Cleaning up {len(active_sessions)} active voice sessions")

        cleanup_results = []

        for session in active_sessions:
            channel_id = int(session['channel_id'])
            session_id = session['id']
            guild_id = int(session['guild_id'])

            # Disconnect any voice client first
            for vc in self.bot.voice_clients:
                if vc.channel and vc.channel.id == channel_id:
                    try:
                        await vc.disconnect(force=False)
                        logger.info(f"Disconnected from voice channel {channel_id}")
                    except Exception as e:
                        logger.error(f"Failed to disconnect from {channel_id}: {e}")

            # Ensure channel is deleted
            deleted = await self.ensure_channel_deleted(channel_id, guild_id)
            cleanup_results.append((channel_id, deleted))

            # Always end database session
            self.db.end_voice_session(session_id)

        # Log summary
        successful = sum(1 for _, success in cleanup_results if success)
        failed = len(cleanup_results) - successful
        logger.info(f"Cleanup complete: {successful} channels deleted, {failed} failed")

        # Process entire deletion queue to catch any orphaned channels
        if self.channels_pending_deletion:
            logger.info(
                f"Processing deletion queue: {len(self.channels_pending_deletion)} "
                f"channels still pending: {self.channels_pending_deletion}"
            )

            successfully_deleted = []
            for pending_channel_id in list(self.channels_pending_deletion):
                # Try to get guild_id from database
                pending_session = self.db.get_active_session_by_channel(str(pending_channel_id))
                pending_guild_id = None

                if pending_session and pending_session.get('guild_id'):
                    pending_guild_id = int(pending_session['guild_id'])

                # Attempt deletion
                deleted = False
                if pending_guild_id:
                    deleted = await self.ensure_channel_deleted(pending_channel_id, pending_guild_id)
                else:
                    # Try all guilds as last resort
                    for guild in self.bot.guilds:
                        try:
                            channel = await guild.fetch_channel(pending_channel_id)
                            if channel:
                                await channel.delete(reason="Orphaned voice channel cleanup")
                                logger.info(f"Deleted orphaned channel {pending_channel_id} from guild {guild.id}")
                                deleted = True
                                break
                        except discord.NotFound:
                            # Channel doesn't exist in this guild, continue
                            continue
                        except discord.HTTPException as e:
                            logger.debug(f"Failed to fetch/delete channel {pending_channel_id} from guild {guild.id}: {e}")
                            continue

                if deleted:
                    successfully_deleted.append(pending_channel_id)

            # Remove successfully deleted channels from pending list
            for deleted_id in successfully_deleted:
                if deleted_id in self.channels_pending_deletion:
                    self.channels_pending_deletion.remove(deleted_id)

            logger.info(
                f"Deletion queue processed: {len(successfully_deleted)} channels deleted, "
                f"{len(self.channels_pending_deletion)} still pending"
            )
        else:
            logger.info("Deletion queue is empty - no pending channels")

    def get_mutual_guilds(self, user_id: int) -> List[discord.Guild]:
        """Get guilds shared between user and bot.

        Args:
            user_id: Discord user ID

        Returns:
            List of shared guilds
        """
        mutual_guilds = []

        for guild in self.bot.guilds:
            member = guild.get_member(user_id)
            if member:
                mutual_guilds.append(guild)

        logger.debug(
            f"Found {len(mutual_guilds)} mutual guilds "
            f"for user {user_id}"
        )
        return mutual_guilds


def get_voice_manager(bot=None) -> VoiceChannelManager:
    """Get or create the global voice manager instance.

    Args:
        bot: Discord bot instance (required for first initialization)

    Returns:
        VoiceChannelManager singleton instance

    Raises:
        ValueError: If bot is not provided on first initialization
    """
    global _voice_manager

    if _voice_manager is None:
        if bot is None:
            raise ValueError("Bot instance required for first voice manager initialization")
        _voice_manager = VoiceChannelManager(bot)
        logger.info("Created singleton VoiceChannelManager instance")

    return _voice_manager


def clear_voice_manager() -> None:
    """Clear the global voice manager instance.

    Used during cleanup or testing.
    """
    global _voice_manager
    _voice_manager = None
    logger.debug("Cleared singleton VoiceChannelManager instance")