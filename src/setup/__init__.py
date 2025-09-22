"""Setup module for Discord-Indexer configuration management.

This module provides terminal-based configuration UI and management
for Discord bot server setup and error handling configuration.
"""

from .configuration_manager import ConfigurationManager, get_configuration_manager

__all__ = ['ConfigurationManager', 'get_configuration_manager']