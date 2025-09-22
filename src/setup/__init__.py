"""Server setup and configuration management for Discord bot.

This module handles the initial configuration process for new Discord servers,
including terminal UI interaction and persistent storage management.
"""

from .server_setup import (
    load_configured_servers,
    is_server_configured,
    get_server_config,
    ensure_server_configured,
    configure_all_servers,
    create_config_tables
)

__all__ = [
    'load_configured_servers',
    'is_server_configured',
    'get_server_config',
    'ensure_server_configured',
    'configure_all_servers',
    'create_config_tables'
]