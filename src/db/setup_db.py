"""Database connection and client management for ChromaDB.

This module handles ChromaDB client initialization and provides centralized
access to the database client throughout the application. The client is
initialized once at startup and reused across all database operations.
"""

import logging
from pathlib import Path
from typing import Optional
import chromadb
from chromadb import Client
from chromadb.errors import ChromaError


logger = logging.getLogger(__name__)

# Module-level client instance
_client: Optional[Client] = None


def initialize_db() -> None:
    """Initialize ChromaDB persistent client.

    Creates a persistent ChromaDB client and stores it for application use.
    Should be called once during application startup.

    Raises:
        OSError: If database directory cannot be created or accessed
        PermissionError: If insufficient permissions for database directory
        ChromaError: If ChromaDB client initialization fails
    """
    global _client

    if _client is not None:
        logger.warning("Database client already initialized")
        return

    # Setup database directory
    db_path = Path(__file__).parent / "chroma_data"

    try:
        db_path.mkdir(exist_ok=True)
        logger.info(f"Database directory ready: {db_path}")
    except PermissionError as e:
        logger.error(f"Insufficient permissions for database directory: {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to create database directory: {e}")
        raise

    # Initialize ChromaDB client
    try:
        _client = chromadb.PersistentClient(path=str(db_path))
        logger.info("ChromaDB client initialized successfully")
    except ChromaError as e:
        logger.error(f"ChromaDB initialization failed: {e}")
        raise
    except (TypeError, ImportError, RuntimeError, AttributeError) as e:
        logger.error(f"Unexpected error during ChromaDB initialization: {e}")
        raise


def get_db() -> Client:
    """Get the initialized ChromaDB client.

    Returns the same client instance throughout the application runtime.
    Must be called after initialize_db() has been executed.

    Returns:
        ChromaDB client instance

    Raises:
        RuntimeError: If client has not been initialized
    """
    if _client is None:
        raise RuntimeError(
            "Database client not initialized. Call initialize_db() first."
        )

    return _client
