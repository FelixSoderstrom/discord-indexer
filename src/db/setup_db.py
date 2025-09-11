"""Database connection and client management for ChromaDB and conversation storage.

This module handles ChromaDB client initialization and provides centralized
access to server-specific database clients throughout the application. Each
server gets its own database with lazy loading for memory efficiency.
Also manages SQLite conversation database initialization.
"""

import logging
from pathlib import Path
from typing import Optional, Dict
import chromadb
from chromadb import Client
from chromadb.errors import ChromaError
from src.db.conversation_db import initialize_conversation_db


logger = logging.getLogger(__name__)

# Module-level server-specific client instances
_clients: Dict[int, Client] = {}


def initialize_db() -> None:
    """Initialize the database directory structure and conversation database.

    Creates the base databases directory structure for server-specific databases.
    Individual server databases are created lazily when first accessed.
    Also initializes the SQLite conversation database for DMAssistant.

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
        
    except PermissionError as e:
        logger.error(f"Insufficient permissions for database directory: {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to create database directory: {e}")
        raise


def get_db(server_id: int) -> Client:
    """Get the ChromaDB client for a specific server.

    Uses lazy loading to create server-specific database clients on demand.
    Each server gets its own isolated database in databases/{server_id}/chroma_data.

    Args:
        server_id: Discord server/guild ID

    Returns:
        ChromaDB client instance for the specified server

    Raises:
        OSError: If database directory cannot be created or accessed
        PermissionError: If insufficient permissions for database directory
        ChromaError: If ChromaDB client initialization fails
    """
    global _clients

    # Return existing client if already initialized
    if server_id in _clients:
        return _clients[server_id]

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
        _clients[server_id] = client
        logger.info(f"ChromaDB client initialized successfully for server {server_id}")
        return client
    except ChromaError as e:
        logger.error(f"ChromaDB initialization failed for server {server_id}: {e}")
        raise
    except (TypeError, ImportError, RuntimeError, AttributeError) as e:
        logger.error(f"Unexpected error during ChromaDB initialization for server {server_id}: {e}")
        raise
