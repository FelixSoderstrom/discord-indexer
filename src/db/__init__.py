"""Database module for Discord message indexer.

This module handles ChromaDB client initialization and management, providing
the core database infrastructure for the application.
"""

from src.db.setup_db import initialize_db, get_db, get_server_embedding_model

__all__ = ["initialize_db", "get_db", "get_server_embedding_model"]
