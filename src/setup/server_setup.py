"""Server setup and configuration management for Discord bot.

Handles initial setup process for new Discord servers, including terminal UI
interaction and persistent configuration storage using SQLite with in-memory caching.
"""

import logging
import sqlite3
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.db.setup_db import get_config_db

logger = logging.getLogger(__name__)

# Global cache of configured server IDs for fast lookup
_configured_servers: List[str] = []


async def fetch_bot_guilds(token: str) -> List[Dict[str, str]]:
    """Fetch bot's guild list using Discord REST API.

    Uses aiohttp to call Discord's REST API and retrieve the list of guilds
    the bot is a member of. This allows pre-startup configuration without
    blocking the async event loop.

    Args:
        token: Discord bot token for authentication

    Returns:
        List of dicts with 'id' and 'name' keys for each guild

    Raises:
        aiohttp.ClientError: If HTTP request fails
        ValueError: If response is invalid or missing required fields
    """
    url = "https://discord.com/api/v10/users/@me/guilds"
    headers = {
        "Authorization": f"Bot {token}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Discord REST API returned status {response.status}: {error_text}")
                    raise aiohttp.ClientError(
                        f"Discord API request failed with status {response.status}: {error_text}"
                    )

                guilds_data = await response.json()

                # Validate and transform response
                guilds = []
                for guild in guilds_data:
                    if 'id' not in guild or 'name' not in guild:
                        logger.warning(f"Skipping invalid guild data: {guild}")
                        continue

                    guilds.append({
                        'id': str(guild['id']),
                        'name': guild['name']
                    })

                logger.info(f"Successfully fetched {len(guilds)} guilds via REST API")
                return guilds

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching guilds from Discord API: {e}")
        raise
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Invalid response from Discord API: {e}")
        raise ValueError(f"Invalid Discord API response: {e}")


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
                SELECT server_id, server_name, message_processing_error_handling, embedding_model_name, created_at, updated_at
                FROM server_configs
                WHERE server_id = ?
            """, (server_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'server_id': row[0],
                    'server_name': row[1],
                    'message_processing_error_handling': row[2],
                    'embedding_model_name': row[3],
                    'created_at': row[4],
                    'updated_at': row[5]
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


def save_server_config(server_id: str, server_name: str, config: Dict[str, str]) -> bool:
    """Save server configuration to database.

    Args:
        server_id: Discord server/guild ID
        server_name: Human-readable server name
        config: Dictionary containing configuration preferences

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        with get_config_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO server_configs
                (server_id, server_name, message_processing_error_handling, embedding_model_name, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                server_id,
                server_name,
                config['error_handling'],
                config.get('embedding_model'),
                datetime.now().isoformat()
            ))
            conn.commit()

        logger.info(f"Saved configuration for server {server_id} ({server_name}): {config}")
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
        if save_server_config(server_id, server_name, config):
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


def update_server_name(server_id: str, server_name: str) -> bool:
    """Update server name in database if it has changed.

    Args:
        server_id: Discord server/guild ID
        server_name: Current server name from Discord API

    Returns:
        True if update successful or not needed, False on error
    """
    try:
        with get_config_db() as conn:
            # Get current stored name
            cursor = conn.execute("""
                SELECT server_name FROM server_configs WHERE server_id = ?
            """, (server_id,))

            row = cursor.fetchone()
            if not row:
                # Server not configured yet
                return True

            stored_name = row[0]

            # Update if name has changed
            if stored_name != server_name:
                conn.execute("""
                    UPDATE server_configs
                    SET server_name = ?, updated_at = ?
                    WHERE server_id = ?
                """, (server_name, datetime.now().isoformat(), server_id))
                conn.commit()

                logger.info(f"Updated server name: {server_id} '{stored_name}' -> '{server_name}'")

        return True

    except sqlite3.Error as e:
        logger.error(f"Failed to update server name for {server_id}: {e}")
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


def configure_all_servers(guilds: List[Dict[str, str]]) -> bool:
    """Configure all unconfigured servers at startup.

    Accepts guild data from Discord REST API and configures unconfigured servers.
    Also updates server names for already-configured servers if they have changed.

    Args:
        guilds: List of dicts with 'id' and 'name' keys from REST API

    Returns:
        True if all servers configured successfully, False if any failed
    """
    unconfigured_servers = []
    configured_servers = []

    # Separate configured and unconfigured servers
    for guild in guilds:
        server_id = guild['id']
        server_name = guild['name']

        if is_server_configured(server_id):
            configured_servers.append((server_id, server_name))
        else:
            unconfigured_servers.append((server_id, server_name))

    # Update names for already-configured servers
    if configured_servers:
        logger.info(f"Updating names for {len(configured_servers)} configured server(s)...")
        for server_id, server_name in configured_servers:
            update_server_name(server_id, server_name)

    # Check if all servers already configured
    if not unconfigured_servers:
        logger.info("All servers are already configured")
        return True

    # Configure unconfigured servers
    print(f"\n" + "=" * 80)
    print(f"DISCORD BOT SETUP")
    print(f"   Found {len(unconfigured_servers)} server(s) that need configuration")
    print("=" * 80)

    success_count = 0
    completed_servers = []

    for i, (server_id, server_name) in enumerate(unconfigured_servers, 1):
        print(f"\nConfiguring server {i}/{len(unconfigured_servers)}")

        try:
            success = configure_new_server(server_id, server_name)
            if success:
                success_count += 1
                completed_servers.append((server_id, server_name))
            else:
                logger.error(f"Failed to configure server {server_name}")

        except KeyboardInterrupt:
            print(f"\n\nConfiguration interrupted by user (Ctrl+C)")
            print(f"Completed servers ({len(completed_servers)}):")
            for sid, sname in completed_servers:
                print(f"  - {sname} ({sid})")

            logger.warning(
                f"Configuration interrupted - {len(completed_servers)}/{len(unconfigured_servers)} "
                f"servers configured successfully"
            )
            return False

    print(f"\n" + "=" * 80)
    print(f"SETUP COMPLETE!")
    print(f"   Configured: {success_count}/{len(unconfigured_servers)} servers")
    print("=" * 80)

    if success_count == len(unconfigured_servers):
        logger.info("All servers configured successfully")
        return True
    else:
        logger.warning(f"Only {success_count}/{len(unconfigured_servers)} servers configured")
        return False