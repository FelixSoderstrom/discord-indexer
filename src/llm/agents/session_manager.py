"""Session manager for DMAssistant conversations.

Manages active user sessions with timeout handling and cleanup notifications.
"""

import asyncio
import logging
from typing import Dict, Optional, Set, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading


logger = logging.getLogger(__name__)


@dataclass
class ServerOption:
    """Available server option for user selection."""
    
    server_id: str
    server_name: str
    last_indexed: Optional[datetime] = None
    message_count: int = 0


@dataclass
class PendingServerSelection:
    """User waiting to select which server to query."""
    
    user_id: str
    original_question: str
    available_servers: List[ServerOption]
    discord_channel: Optional[object] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize created_at if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def is_expired(self, timeout_minutes: int = 5) -> bool:
        """Check if server selection has expired."""
        timeout_delta = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.created_at > timeout_delta


@dataclass
class UserSession:
    """Active user session with timeout tracking."""
    
    user_id: str
    server_id: str
    last_activity: datetime
    discord_channel: Optional[object] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize created_at if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def is_expired(self, timeout_minutes: int = 5) -> bool:
        """Check if session has expired due to inactivity."""
        timeout_delta = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.last_activity > timeout_delta
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()


class SessionManager:
    """Manages active DMAssistant user sessions with timeout handling."""
    
    def __init__(self, timeout_minutes: int = 5, cleanup_interval: int = 60):
        """Initialize session manager.
        
        Args:
            timeout_minutes: Minutes of inactivity before session expires
            cleanup_interval: Seconds between cleanup runs
        """
        self.timeout_minutes = timeout_minutes
        self.cleanup_interval = cleanup_interval
        
        # Thread-safe session tracking
        self._sessions: Dict[str, UserSession] = {}
        self._pending_selections: Dict[str, PendingServerSelection] = {}
        self._lock = threading.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"SessionManager initialized (timeout={timeout_minutes}m, cleanup={cleanup_interval}s)")
    
    def create_session(self, user_id: str, server_id: str, discord_channel=None) -> UserSession:
        """Create a new user session.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server ID
            discord_channel: Discord channel for notifications
            
        Returns:
            UserSession object
        """
        with self._lock:
            session = UserSession(
                user_id=user_id,
                server_id=server_id,
                last_activity=datetime.now(),
                discord_channel=discord_channel
            )
            
            self._sessions[user_id] = session
            logger.info(f"Created session for user {user_id} in server {server_id}")
            return session
    
    def get_session(self, user_id: str) -> Optional[UserSession]:
        """Get active session for user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            UserSession if active, None otherwise
        """
        with self._lock:
            return self._sessions.get(user_id)
    
    def has_active_session(self, user_id: str) -> bool:
        """Check if user has an active session.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if user has active session
        """
        with self._lock:
            session = self._sessions.get(user_id)
            return session is not None and not session.is_expired(self.timeout_minutes)
    
    def update_session_activity(self, user_id: str) -> bool:
        """Update session activity timestamp.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if session updated, False if no active session
        """
        with self._lock:
            session = self._sessions.get(user_id)
            if session and not session.is_expired(self.timeout_minutes):
                session.update_activity()
                logger.debug(f"Updated activity for user {user_id}")
                return True
            return False
    
    def end_session(self, user_id: str) -> bool:
        """Manually end a user session.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if session ended, False if no active session
        """
        with self._lock:
            if user_id in self._sessions:
                del self._sessions[user_id]
                logger.info(f"Ended session for user {user_id}")
                return True
            return False
    
    def add_pending_server_selection(self, user_id: str, question: str, servers: List[ServerOption], discord_channel=None) -> None:
        """Add user to server selection waitlist.
        
        Args:
            user_id: Discord user ID
            question: Original question from user
            servers: List of available servers to choose from
            discord_channel: Discord channel for responses
        """
        with self._lock:
            selection = PendingServerSelection(
                user_id=user_id,
                original_question=question,
                available_servers=servers,
                discord_channel=discord_channel
            )
            
            self._pending_selections[user_id] = selection
            logger.info(f"Added user {user_id} to server selection waitlist with {len(servers)} server options")
    
    def get_pending_server_selection(self, user_id: str) -> Optional[PendingServerSelection]:
        """Get pending server selection for user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            PendingServerSelection if waiting, None otherwise
        """
        with self._lock:
            return self._pending_selections.get(user_id)
    
    def has_pending_server_selection(self, user_id: str) -> bool:
        """Check if user has pending server selection.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if user is waiting for server selection
        """
        with self._lock:
            selection = self._pending_selections.get(user_id)
            return selection is not None and not selection.is_expired(self.timeout_minutes)
    
    def complete_server_selection(self, user_id: str) -> Optional[PendingServerSelection]:
        """Remove user from server selection waitlist and return their selection data.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            PendingServerSelection data if found, None otherwise
        """
        with self._lock:
            if user_id in self._pending_selections:
                selection = self._pending_selections.pop(user_id)
                logger.info(f"Completed server selection for user {user_id}")
                return selection
            return None
    
    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._running:
            logger.warning("Cleanup task already running")
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session cleanup task started")
    
    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Session cleanup task stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background loop to clean up expired sessions."""
        logger.info("Session cleanup loop started")
        
        while self._running:
            try:
                await self._cleanup_expired_sessions()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in session cleanup loop: {e}")
                await asyncio.sleep(5.0)
    
    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions and server selections, notify users."""
        expired_sessions = []
        expired_selections = []
        
        # Find expired sessions and server selections
        with self._lock:
            # Clean up expired active sessions
            for user_id, session in list(self._sessions.items()):
                if session.is_expired(self.timeout_minutes):
                    expired_sessions.append(session)
                    del self._sessions[user_id]
            
            # Clean up expired server selections
            for user_id, selection in list(self._pending_selections.items()):
                if selection.is_expired(self.timeout_minutes):
                    expired_selections.append(selection)
                    del self._pending_selections[user_id]
        
        # Notify users of session expiry
        for session in expired_sessions:
            logger.info(f"Session expired for user {session.user_id} after {self.timeout_minutes} minutes")
            
            if session.discord_channel:
                try:
                    await session.discord_channel.send(
                        f"⏰ **Session Expired**: Your conversation has been automatically ended "
                        f"due to {self.timeout_minutes} minutes of inactivity. "
                        f"Use `!ask` to start a new conversation."
                    )
                except Exception as e:
                    logger.error(f"Error notifying user {session.user_id} of session expiry: {e}")
        
        # Notify users of server selection timeout
        for selection in expired_selections:
            logger.info(f"Server selection expired for user {selection.user_id} after {self.timeout_minutes} minutes")
            
            if selection.discord_channel:
                try:
                    await selection.discord_channel.send(
                        f"⏰ **Server Selection Timeout**: You took too long to select a server. "
                        f"Your question was: \"{selection.original_question[:100]}{'...' if len(selection.original_question) > 100 else ''}\"\n\n"
                        f"Use `!ask` again to restart."
                    )
                except Exception as e:
                    logger.error(f"Error notifying user {selection.user_id} of server selection timeout: {e}")
    
    def get_session_count(self) -> int:
        """Get total number of active sessions."""
        with self._lock:
            return len(self._sessions)
    
    def get_session_stats(self) -> Dict[str, int]:
        """Get session statistics.
        
        Returns:
            Dictionary with session statistics
        """
        with self._lock:
            active_count = 0
            expired_count = 0
            
            for session in self._sessions.values():
                if session.is_expired(self.timeout_minutes):
                    expired_count += 1
                else:
                    active_count += 1
            
            # Count pending server selections
            pending_active = 0
            pending_expired = 0
            
            for selection in self._pending_selections.values():
                if selection.is_expired(self.timeout_minutes):
                    pending_expired += 1
                else:
                    pending_active += 1
            
            return {
                "active_sessions": active_count,
                "expired_sessions": expired_count,
                "total_sessions": len(self._sessions),
                "pending_server_selections": pending_active,
                "expired_server_selections": pending_expired,
                "total_pending_selections": len(self._pending_selections),
                "timeout_minutes": self.timeout_minutes
            }


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance.
    
    Returns:
        SessionManager instance
    """
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager()
    
    return _session_manager


def initialize_session_manager(timeout_minutes: int = 5, cleanup_interval: int = 60) -> SessionManager:
    """Initialize the global session manager.
    
    Args:
        timeout_minutes: Minutes of inactivity before session expires
        cleanup_interval: Seconds between cleanup runs
        
    Returns:
        SessionManager instance
    """
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager(timeout_minutes, cleanup_interval)
        logger.info("Session manager initialized during startup")
    
    return _session_manager