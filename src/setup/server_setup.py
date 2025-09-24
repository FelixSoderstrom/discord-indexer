"""Server setup and configuration management for Discord bot.

Handles initial setup process for new Discord servers, including terminal UI
interaction and persistent configuration storage using SQLite with in-memory caching.
"""

import logging
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.db.setup_db import get_config_db

logger = logging.getLogger(__name__)

# Global cache of configured server IDs for fast lookup
_configured_servers: List[str] = []



def load_configured_servers() -> List[str]:
    """Load all configured server IDs into memory cache.
    
    Returns:
        List of server IDs that have been configured
    """
    global _configured_servers
    
    try:
        with get_config_db() as conn:
            cursor = conn.execute("SELECT server_id FROM server_configs")
            _configured_servers = [row[0] for row in cursor.fetchall()]
            
        logger.info(f"Loaded {len(_configured_servers)} configured servers into cache")
        return _configured_servers
        
    except sqlite3.Error as e:
        logger.error(f"Failed to load configured servers: {e}")
        _configured_servers = []
        return []


def is_server_configured(server_id: str) -> bool:
    """Check if server is configured using in-memory cache.
    
    Args:
        server_id: Discord server/guild ID
        
    Returns:
        True if server is configured, False otherwise
    """
    return server_id in _configured_servers


def get_server_config(server_id: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific server.
    
    Args:
        server_id: Discord server/guild ID
        
    Returns:
        Dictionary of server configuration or None if not found
    """
    try:
        with get_config_db() as conn:
            cursor = conn.execute("""
                SELECT server_id, message_processing_error_handling, embedding_model_name, created_at, updated_at
                FROM server_configs 
                WHERE server_id = ?
            """, (server_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'server_id': row[0],
                    'message_processing_error_handling': row[1],
                    'embedding_model_name': row[2],
                    'created_at': row[3],
                    'updated_at': row[4]
                }
            return None
            
    except sqlite3.Error as e:
        logger.error(f"Failed to get server config for {server_id}: {e}")
        return None


def run_setup_terminal_ui(server_id: str, server_name: str) -> Dict[str, str]:
    """Run simple terminal UI for server configuration.
    
    Args:
        server_id: Discord server/guild ID
        server_name: Human-readable server name
        
    Returns:
        Dictionary with error handling and embedding model preferences
    """
    print(f"\n" + "=" * 80)
    print(f"🤖 CONFIGURING SERVER: {server_name}")
    print(f"   Server ID: {server_id}")
    print("=" * 80)
    
    # Error handling configuration
    print("The bot needs to know how to handle processing errors.")
    print("\nWhen a message fails to process, should the bot:")
    print("1. Skip that message and continue with others (recommended)")
    print("2. Stop processing and shut down the application")
    
    error_handling = None
    while error_handling is None:
        choice = input(f"\nEnter choice for {server_name} (1 or 2): ").strip()
        
        if choice == "1":
            print(f"✅ {server_name}: Will skip failed messages and continue processing")
            error_handling = "skip"
        elif choice == "2":
            print(f"✅ {server_name}: Will stop processing when any message fails")
            error_handling = "stop"
        else:
            print("❌ Please enter 1 or 2")
    
    # Embedding model configuration
    print(f"\n🧠 EMBEDDING MODEL CONFIGURATION")
    print("Choose the embedding model for semantic search:")
    print("1. Use global default (recommended)")
    print("2. Use BGE-large-en-v1.5 (high accuracy, requires GPU)")
    print("3. Use lightweight model (faster, less accurate)")
    print("4. Custom model name")
    
    embedding_model = None
    while embedding_model is None:
        choice = input(f"\nEnter choice for {server_name} (1-4): ").strip()
        
        if choice == "1":
            embedding_model = "default"
            print(f"✅ {server_name}: Will use global default embedding model")
        elif choice == "2":
            embedding_model = "BAAI/bge-large-en-v1.5"
            print(f"✅ {server_name}: Will use BGE-large-en-v1.5 (GPU required)")
        elif choice == "3":
            embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
            print(f"✅ {server_name}: Will use lightweight MiniLM model")
        elif choice == "4":
            custom_model = input("Enter custom model name: ").strip()
            if custom_model:
                embedding_model = custom_model
                print(f"✅ {server_name}: Will use custom model {custom_model}")
            else:
                print("❌ Please enter a valid model name")
        else:
            print("❌ Please enter 1, 2, 3, or 4")
    
    return {
        'error_handling': error_handling,
        'embedding_model': embedding_model
    }


def save_server_config(server_id: str, config: Dict[str, str]) -> bool:
    """Save server configuration to database.
    
    Args:
        server_id: Discord server/guild ID
        config: Dictionary containing configuration preferences
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        with get_config_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO server_configs 
                (server_id, message_processing_error_handling, embedding_model_name, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                server_id, 
                config['error_handling'],
                config.get('embedding_model'),
                datetime.now().isoformat()
            ))
            conn.commit()
            
        logger.info(f"Saved configuration for server {server_id}: {config}")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Failed to save server config for {server_id}: {e}")
        return False


def add_server_to_cache(server_id: str) -> None:
    """Add newly configured server to in-memory cache.
    
    Args:
        server_id: Discord server/guild ID to add
    """
    global _configured_servers
    
    if server_id not in _configured_servers:
        _configured_servers.append(server_id)
        logger.info(f"Added server {server_id} to configured servers cache")


def configure_new_server(server_id: str, server_name: str) -> bool:
    """Complete configuration process for a new server.
    
    Args:
        server_id: Discord server/guild ID
        server_name: Human-readable server name
        
    Returns:
        True if configuration completed successfully
    """
    try:
        # Run terminal UI
        config = run_setup_terminal_ui(server_id, server_name)
        
        # Save to database
        if save_server_config(server_id, config):
            # Update in-memory cache
            add_server_to_cache(server_id)
            print(f"✅ Server {server_name} configured successfully!")
            return True
        else:
            print(f"❌ Failed to save configuration for {server_name}")
            return False
            
    except KeyboardInterrupt:
        print(f"\n❌ Configuration cancelled for {server_name}")
        return False
    except Exception as e:
        logger.error(f"Configuration failed for server {server_id}: {e}")
        print(f"❌ Configuration failed: {e}")
        return False


def ensure_server_configured(server_id: str, server_name: str) -> bool:
    """Ensure server is configured before processing messages.
    
    This is the main junction point function that should be called from both
    historical and real-time processing flows to guarantee server configuration.
    
    Args:
        server_id: Discord server/guild ID
        server_name: Human-readable server name
        
    Returns:
        True if server is configured (or was successfully configured), False otherwise
    """
    # Quick check using in-memory cache
    if is_server_configured(server_id):
        return True
    
    logger.warning(f"Server {server_id} ({server_name}) not configured - running setup")
    
    # Run configuration process
    success = configure_new_server(server_id, server_name)
    
    if success:
        logger.info(f"Server {server_id} configured successfully")
        return True
    else:
        logger.error(f"Failed to configure server {server_id}")
        return False


def configure_all_servers(guilds) -> bool:
    """Configure all unconfigured servers at startup.
    
    Args:
        guilds: List of Discord guild objects from bot.guilds
        
    Returns:
        True if all servers configured successfully, False if any failed
    """
    unconfigured_servers = []
    
    # Find servers that need configuration
    for guild in guilds:
        server_id = str(guild.id)
        if not is_server_configured(server_id):
            unconfigured_servers.append((server_id, guild.name))
    
    if not unconfigured_servers:
        logger.info("All servers are already configured")
        return True
    
    print(f"\n" + "=" * 80)
    print(f"🚀 DISCORD BOT SETUP")
    print(f"   Found {len(unconfigured_servers)} server(s) that need configuration")
    print("=" * 80)
    
    success_count = 0
    
    for i, (server_id, server_name) in enumerate(unconfigured_servers, 1):
        print(f"\n📋 Configuring server {i}/{len(unconfigured_servers)}")
        
        success = configure_new_server(server_id, server_name)
        if success:
            success_count += 1
        else:
            logger.error(f"Failed to configure server {server_name}")
    
    print(f"\n" + "=" * 80)
    print(f"🎉 SETUP COMPLETE!")
    print(f"   Configured: {success_count}/{len(unconfigured_servers)} servers")
    print("=" * 80)
    
    if success_count == len(unconfigured_servers):
        logger.info("All servers configured successfully")
        return True
    else:
        logger.warning(f"Only {success_count}/{len(unconfigured_servers)} servers configured")
        return False