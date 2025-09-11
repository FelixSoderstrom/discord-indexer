"""SQLite database management for DMAssistant conversation persistence.

This module handles conversation storage and retrieval for the DMAssistant system,
providing server-isolated conversation history with proper user tracking and
message persistence across bot restarts.
"""

import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import threading
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class ConversationDatabase:
    """SQLite database manager for persistent conversation storage.
    
    Provides thread-safe operations for storing and retrieving conversation
    history with server isolation. Each conversation is tracked by user_id
    and server_id to prevent cross-server data leakage.
    
    Database Schema:
        conversations:
            - id: INTEGER PRIMARY KEY AUTOINCREMENT
            - user_id: TEXT NOT NULL (Discord user ID)
            - server_id: TEXT NOT NULL (Discord server/guild ID)
            - role: TEXT NOT NULL ('user' or 'assistant')
            - content: TEXT NOT NULL (Message content)
            - timestamp: DATETIME DEFAULT CURRENT_TIMESTAMP
            - session_id: TEXT (Optional session grouping)
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize conversation database connection.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default path.
        """
        if db_path is None:
            db_path = Path(__file__).parent / "databases" / "conversations.sqlite3"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        
        # Initialize database schema
        self._initialize_schema()
        
        logger.info(f"ConversationDatabase initialized: {self.db_path}")
    
    def _initialize_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create conversations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    server_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT
                )
            ''')
            
            # Create indexes for efficient queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_server 
                ON conversations(user_id, server_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON conversations(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_session 
                ON conversations(session_id)
            ''')
            
            conn.commit()
            logger.debug("Database schema initialized successfully")
    
    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection with proper cleanup."""
        with self._lock:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
    
    def add_message(
        self, 
        user_id: str, 
        server_id: str, 
        role: str, 
        content: str,
        session_id: Optional[str] = None
    ) -> bool:
        """Add a message to conversation history.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server/guild ID  
            role: Message role ('user' or 'assistant')
            content: Message content
            session_id: Optional session identifier for grouping
            
        Returns:
            True if message added successfully, False otherwise
        """
        if role not in ('user', 'assistant'):
            logger.error(f"Invalid role '{role}'. Must be 'user' or 'assistant'")
            return False
            
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversations 
                    (user_id, server_id, role, content, session_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, server_id, role, content, session_id))
                
                conn.commit()
                
                logger.debug(
                    f"Added {role} message for user {user_id} in server {server_id}"
                )
                return True
                
        except sqlite3.IntegrityError as e:
            logger.warning(f"Duplicate message not inserted: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error adding message: {e}")
            return False
    
    def get_conversation_history(
        self,
        user_id: str,
        server_id: str,
        limit: int = 50,
        before_timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a user in a specific server.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server/guild ID
            limit: Maximum number of messages to return
            before_timestamp: Only return messages before this timestamp
            
        Returns:
            List of message dictionaries in chronological order
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if before_timestamp:
                    cursor.execute('''
                        SELECT user_id, server_id, role, content, timestamp, session_id
                        FROM conversations
                        WHERE user_id = ? AND server_id = ? AND timestamp < ?
                        ORDER BY timestamp ASC
                        LIMIT ?
                    ''', (user_id, server_id, before_timestamp, limit))
                else:
                    cursor.execute('''
                        SELECT user_id, server_id, role, content, timestamp, session_id
                        FROM conversations
                        WHERE user_id = ? AND server_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (user_id, server_id, limit))
                
                rows = cursor.fetchall()
                
                messages = []
                for row in rows:
                    messages.append({
                        'user_id': row['user_id'],
                        'server_id': row['server_id'],
                        'role': row['role'],
                        'content': row['content'],
                        'timestamp': row['timestamp'],
                        'session_id': row['session_id']
                    })
                
                logger.debug(
                    f"Retrieved {len(messages)} messages for user {user_id} "
                    f"in server {server_id}"
                )
                return messages
                
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving conversation history: {e}")
            return []
    
    def search_conversation_history(
        self,
        user_id: str,
        server_id: str,
        query_terms: List[str],
        limit: int = 20,
        days_back: int = 90
    ) -> List[Dict[str, Any]]:
        """Search conversation history using full-text search for RAG context.
        
        Searches through conversation history to find relevant messages that
        might provide additional context for the current question. Uses keyword
        matching for efficiency (semantic search can be added later with embeddings).
        
        Args:
            user_id: Discord user ID
            server_id: Discord server/guild ID  
            query_terms: List of search terms extracted from user's question
            limit: Maximum number of relevant messages to return
            days_back: How many days back to search (default 90 days)
            
        Returns:
            List of relevant message dictionaries sorted by relevance/recency
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Build search query with term matching
                search_conditions = []
                params = [user_id, server_id]
                
                for term in query_terms[:5]:  # Limit to 5 terms for performance
                    search_conditions.append("content LIKE ?")
                    params.append(f"%{term}%")
                
                if not search_conditions:
                    return []
                
                # Build the SQL query
                search_sql = f'''
                    SELECT user_id, server_id, role, content, timestamp, session_id
                    FROM conversations
                    WHERE user_id = ? AND server_id = ? 
                    AND ({" OR ".join(search_conditions)})
                    AND timestamp > datetime('now', '-{days_back} days')
                    ORDER BY timestamp DESC
                    LIMIT ?
                '''
                
                params.append(limit)
                cursor.execute(search_sql, params)
                
                rows = cursor.fetchall()
                
                messages = []
                for row in rows:
                    messages.append({
                        'user_id': row['user_id'],
                        'server_id': row['server_id'], 
                        'role': row['role'],
                        'content': row['content'],
                        'timestamp': row['timestamp'],
                        'session_id': row['session_id']
                    })
                
                logger.debug(
                    f"Found {len(messages)} relevant messages for search terms: {query_terms[:3]}..."
                )
                return messages
                
        except sqlite3.Error as e:
            logger.error(f"Database error searching conversation history: {e}")
            return []
    
    def clear_user_conversation_history(
        self,
        user_id: str,
        server_id: str
    ) -> bool:
        """Clear all conversation history for a user in a specific server.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server/guild ID
            
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM conversations
                    WHERE user_id = ? AND server_id = ?
                ''', (user_id, server_id))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(
                    f"Cleared {deleted_count} messages for user {user_id} "
                    f"in server {server_id}"
                )
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database error clearing conversation history: {e}")
            return False
    
    def get_conversation_count(self, user_id: str, server_id: str) -> int:
        """Get total number of messages for a user in a specific server.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server/guild ID
            
        Returns:
            Number of messages in conversation history
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) as count
                    FROM conversations
                    WHERE user_id = ? AND server_id = ?
                ''', (user_id, server_id))
                
                row = cursor.fetchone()
                return row['count'] if row else 0
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting conversation count: {e}")
            return 0
    
    def get_active_users(self, server_id: str, hours: int = 24) -> List[str]:
        """Get list of users with recent conversation activity.
        
        Args:
            server_id: Discord server/guild ID
            hours: Number of hours to look back for activity
            
        Returns:
            List of user IDs with recent activity
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT user_id
                    FROM conversations
                    WHERE server_id = ? 
                    AND timestamp > datetime('now', '-{} hours')
                    ORDER BY timestamp DESC
                '''.format(hours), (server_id,))
                
                rows = cursor.fetchall()
                return [row['user_id'] for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting active users: {e}")
            return []
    
    def cleanup_old_conversations(self, days: int = 30) -> int:
        """Remove conversations older than specified days.
        
        Args:
            days: Number of days to retain conversations
            
        Returns:
            Number of messages deleted
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM conversations
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old conversation messages")
                
                return deleted_count
                
        except sqlite3.Error as e:
            logger.error(f"Database error during cleanup: {e}")
            return 0
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics for monitoring.
        
        Returns:
            Dictionary with database statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total messages
                cursor.execute('SELECT COUNT(*) as total FROM conversations')
                total_messages = cursor.fetchone()['total']
                
                # Unique users
                cursor.execute('SELECT COUNT(DISTINCT user_id) as users FROM conversations')
                unique_users = cursor.fetchone()['users']
                
                # Unique servers
                cursor.execute('SELECT COUNT(DISTINCT server_id) as servers FROM conversations')
                unique_servers = cursor.fetchone()['servers']
                
                # Messages today
                cursor.execute('''
                    SELECT COUNT(*) as today 
                    FROM conversations
                    WHERE date(timestamp) = date('now')
                ''')
                messages_today = cursor.fetchone()['today']
                
                return {
                    'total_messages': total_messages,
                    'unique_users': unique_users,
                    'unique_servers': unique_servers,
                    'messages_today': messages_today
                }
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting stats: {e}")
            return {}


# Global conversation database instance
_conversation_db: Optional[ConversationDatabase] = None


def get_conversation_db() -> ConversationDatabase:
    """Get the global conversation database instance.
    
    Uses lazy initialization to create the database connection
    only when first needed.
    
    Returns:
        ConversationDatabase instance
    """
    global _conversation_db
    
    if _conversation_db is None:
        _conversation_db = ConversationDatabase()
    
    return _conversation_db


def initialize_conversation_db() -> None:
    """Initialize the conversation database explicitly.
    
    This can be called during application startup to ensure
    the database is ready before first use.
    """
    global _conversation_db
    
    if _conversation_db is None:
        _conversation_db = ConversationDatabase()
        logger.info("Conversation database initialized during startup")