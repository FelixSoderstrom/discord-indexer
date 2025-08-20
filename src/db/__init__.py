"""Database module for Discord message indexer.

This module handles database connections, session management, and provides
the core database infrastructure for the application.
"""

from .setup_db import get_db

__all__ = ['get_db']
