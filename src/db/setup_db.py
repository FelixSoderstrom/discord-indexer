"""Database connection and client management for ChromaDB and conversation storage.

This module handles ChromaDB client initialization and provides centralized
access to server-specific database clients throughout the application. Each
server gets its own database with lazy loading for memory efficiency.
Also manages SQLite conversation database initialization and server configuration storage.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional, Dict
import chromadb
from chromadb import Client
from chromadb.errors import ChromaError
from src.db.conversation_db import initialize_conversation_db


logger = logging.getLogger(__name__)

# Module-level server-specific client instances
_clients: Dict[str, Client] = {}


def initialize_db() -> None:
    """Initialize the database directory structure and conversation database.

    Creates the base databases directory structure for server-specific databases.
    Individual server databases are created lazily when first accessed.
    Also initializes the SQLite conversation database for DMAssistant and server configuration storage.

    Raises:
        OSError: If database directory cannot be created or accessed
        PermissionError: If insufficient permissions for database directory
    """
    # Setup base databases directory
    databases_path = Path(__file__).parent / "databases"

    try:
        databases_path.mkdir(exist_ok=True)
        logger.info(f"Database directory structure ready: {databases_path}")
        
        # Initialize conversation database
        initialize_conversation_db()
        logger.info("Conversation database initialized successfully")
        
        # Initialize server configuration database
        _initialize_config_db()
        logger.info("Server configuration database initialized successfully")
        
    except PermissionError as e:
        logger.error(f"Insufficient permissions for database directory: {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to create database directory: {e}")
        raise


def get_db(server_id: int, embedding_model: Optional[str] = None) -> Client:
    """Get the ChromaDB client for a specific server.

    Uses lazy loading to create server-specific database clients on demand.
    Each server gets its own isolated database in databases/{server_id}/chroma_data.

    Args:
        server_id: Discord server/guild ID
        embedding_model: Optional embedding model name for custom embedding function

    Returns:
        ChromaDB client instance for the specified server

    Raises:
        OSError: If database directory cannot be created or accessed
        PermissionError: If insufficient permissions for database directory
        ChromaError: If ChromaDB client initialization fails
    """
    global _clients

    # Create cache key that includes embedding model for proper isolation
    cache_key = f"{server_id}_{embedding_model or 'default'}"
    
    # Return existing client if already initialized
    if cache_key in _clients:
        return _clients[cache_key]

    # Create server-specific database directory
    server_db_path = Path(__file__).parent / "databases" / str(server_id) / "chroma_data"

    try:
        server_db_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Server {server_id} database directory ready: {server_db_path}")
    except PermissionError as e:
        logger.error(f"Insufficient permissions for server {server_id} database directory: {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to create server {server_id} database directory: {e}")
        raise

    # Initialize ChromaDB client for this server
    try:
        client = chromadb.PersistentClient(path=str(server_db_path))
        _clients[cache_key] = client
        logger.info(f"ChromaDB client initialized successfully for server {server_id} with embedding model: {embedding_model or 'default'}")
        return client
    except ChromaError as e:
        logger.error(f"ChromaDB initialization failed for server {server_id}: {e}")
        raise
    except (TypeError, ImportError, RuntimeError, AttributeError) as e:
        logger.error(f"Unexpected error during ChromaDB initialization for server {server_id}: {e}")
        raise


def _initialize_config_db() -> None:
    """Initialize the SQLite database for server configurations."""
    config_db_path = Path(__file__).parent / "databases" / "server_configs.db"

    try:
        # Create database file and tables
        with sqlite3.connect(config_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS server_configs (
                    server_id TEXT PRIMARY KEY,
                    server_name TEXT DEFAULT NULL,
                    message_processing_error_handling TEXT DEFAULT 'skip',
                    embedding_model_name TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add embedding_model_name column if it doesn't exist (for existing databases)
            try:
                conn.execute("""
                    ALTER TABLE server_configs
                    ADD COLUMN embedding_model_name TEXT DEFAULT NULL
                """)
            except sqlite3.OperationalError:
                # Column already exists
                pass

            # Add server_name column if it doesn't exist (for existing databases)
            try:
                conn.execute("""
                    ALTER TABLE server_configs
                    ADD COLUMN server_name TEXT DEFAULT NULL
                """)
            except sqlite3.OperationalError:
                # Column already exists
                pass

            conn.commit()

        logger.info(f"Server configuration database ready: {config_db_path}")

    except sqlite3.Error as e:
        logger.error(f"Failed to initialize server configuration database: {e}")
        raise


def get_config_db() -> sqlite3.Connection:
    """Get SQLite connection for server configuration database.
    
    Returns:
        SQLite connection to the server configuration database
        
    Raises:
        sqlite3.Error: If database connection fails
    """
    config_db_path = Path(__file__).parent / "databases" / "server_configs.db"
    
    try:
        conn = sqlite3.connect(config_db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn
    except sqlite3.Error as e:
        logger.error(f"Failed to connect to server configuration database: {e}")
        raise


def get_server_embedding_model(server_id: int) -> Optional[str]:
    """Get the configured embedding model for a server.
    
    Args:
        server_id: Discord server/guild ID
        
    Returns:
        Embedding model name or None if not configured/using default
    """
    try:
        with get_config_db() as conn:
            cursor = conn.execute("""
                SELECT embedding_model_name 
                FROM server_configs 
                WHERE server_id = ?
            """, (str(server_id),))
            
            row = cursor.fetchone()
            if row and row[0] and row[0] != "default":
                return row[0]
            return None
            
    except sqlite3.Error as e:
        logger.error(f"Failed to get embedding model for server {server_id}: {e}")
        return None
