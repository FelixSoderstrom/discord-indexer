"""Configuration Agent for Discord bot server setup and management.

This module provides comprehensive configuration management for Discord servers,
including one-time setup processes, terminal-based configuration UI, persistent
storage in ChromaDB, and global in-memory settings management.
"""

import logging
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import threading
from enum import Enum
import re

import chromadb
from chromadb import Client
from chromadb.errors import ChromaError

from src.llm.utils import ensure_model_available, health_check, get_ollama_client
from src.db.setup_db import get_db
from src.exceptions.message_processing import DatabaseConnectionError

try:
    from src.config.settings import settings
except ImportError:
    # Fallback for direct script execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from src.config.settings import settings


class ConfigurationStatus(Enum):
    """Configuration status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConfigurationOption:
    """Represents a single configuration option."""

    key: str
    display_name: str
    description: str
    data_type: str  # 'string', 'integer', 'boolean', 'choice'
    default_value: Any = None
    required: bool = True
    choices: Optional[List[str]] = None
    validation_pattern: Optional[str] = None
    category: str = "general"


@dataclass
class ServerConfiguration:
    """Represents complete server configuration."""

    server_id: str
    server_name: str
    configuration_options: Dict[str, Any]
    setup_status: ConfigurationStatus
    created_at: datetime
    updated_at: datetime
    setup_version: str = "1.0"


class ConfigurationAgent:
    """
    Discord bot server configuration management agent.

    Handles one-time setup processes, terminal-based configuration UI,
    persistent storage per server, and global in-memory settings management.
    Designed to be extensible for easy addition of new configuration options.
    """

    # Global in-memory settings dictionary accessible throughout codebase
    _global_settings: Dict[str, Dict[str, Any]] = {}
    _settings_lock = threading.Lock()

    def __init__(self):
        """
        Initialize the Configuration Agent.
        """
        self.logger = logging.getLogger(__name__)

        # ChromaDB collections for configuration storage
        self._config_collection_name = "server_configurations"
        self._registry_collection_name = "configuration_registry"
        self._history_collection_name = "configuration_history"

        # Initialize configuration options registry
        self._configuration_registry = self._load_configuration_registry()

        # Load existing server configurations into memory
        self._load_configurations_to_memory()

        self.logger.info("ConfigurationAgent initialized successfully")

    def _get_collection(self, server_id: str, collection_name: str):
        """Get ChromaDB collection for a specific server."""
        try:
            client = get_db(int(server_id))
            return client.get_or_create_collection(name=collection_name)
        except (ChromaError, ValueError) as e:
            self.logger.error(f"Error accessing collection {collection_name} for server {server_id}: {e}")
            raise

    def _get_global_collection(self, collection_name: str):
        """Get ChromaDB collection for global data (using server_id 0)."""
        try:
            client = get_db(0)  # Use server_id 0 for global configuration data
            return client.get_or_create_collection(name=collection_name)
        except (ChromaError, ValueError) as e:
            self.logger.error(f"Error accessing global collection {collection_name}: {e}")
            raise

    def _load_configuration_registry(self) -> Dict[str, ConfigurationOption]:
        """Load configuration options from ChromaDB or initialize defaults."""
        try:
            collection = self._get_global_collection(self._registry_collection_name)

            registry = {}

            try:
                # Get all configuration options from ChromaDB
                results = collection.get()

                if results['documents']:
                    for i, doc in enumerate(results['documents']):
                        option_data = json.loads(doc)
                        option = ConfigurationOption(
                            key=option_data['key'],
                            display_name=option_data['display_name'],
                            description=option_data['description'],
                            data_type=option_data['data_type'],
                            default_value=option_data.get('default_value'),
                            required=option_data.get('required', True),
                            choices=option_data.get('choices'),
                            validation_pattern=option_data.get('validation_pattern'),
                            category=option_data.get('category', 'general')
                        )
                        registry[option.key] = option

                    # Merge with default options to ensure new options are available
                    default_options = self._create_default_configuration_options()
                    for key, option in default_options.items():
                        if key not in registry:
                            registry[key] = option

                    # Save updated registry if we added new options
                    if len(registry) > len(results['documents']):
                        self._save_configuration_registry(registry)
                else:
                    # Collection is empty, initialize with defaults
                    registry = self._create_default_configuration_options()
                    self._save_configuration_registry(registry)

            except Exception:
                # Collection doesn't exist or is empty, create defaults
                registry = self._create_default_configuration_options()
                self._save_configuration_registry(registry)

            self.logger.info(f"Loaded {len(registry)} configuration options")
            return registry

        except (ChromaError, ValueError) as e:
            self.logger.error(f"Error loading configuration registry: {e}")
            # Return default options as fallback
            return self._create_default_configuration_options()

    def _create_default_configuration_options(self) -> Dict[str, ConfigurationOption]:
        """Create default configuration options for Discord bot setup."""
        default_options = {
            'message_processing_error_handling': ConfigurationOption(
                key='message_processing_error_handling',
                display_name='Message Processing Error Handling',
                description='What should the bot do when message processing fails?',
                data_type='choice',
                choices=['skip', 'stop'],
                default_value='skip',
                required=True,
                category='setup'
            ),
            'database_error_handling': ConfigurationOption(
                key='database_error_handling',
                display_name='Database Error Handling',
                description='What should the bot do when database operations fail?',
                data_type='choice',
                choices=['skip', 'stop'],
                default_value='skip',
                required=True,
                category='setup'
            ),
            'llm_error_handling': ConfigurationOption(
                key='llm_error_handling',
                display_name='LLM Processing Error Handling',
                description='What should the bot do when AI model processing fails?',
                data_type='choice',
                choices=['skip', 'stop'],
                default_value='skip',
                required=True,
                category='setup'
            )
        }

        return default_options

    def _save_configuration_registry(self, registry: Dict[str, ConfigurationOption]) -> None:
        """Save configuration options registry to ChromaDB."""
        try:
            collection = self._get_global_collection(self._registry_collection_name)

            # Prepare documents for upsert
            documents = []
            ids = []

            for option in registry.values():
                option_data = {
                    'key': option.key,
                    'display_name': option.display_name,
                    'description': option.description,
                    'data_type': option.data_type,
                    'default_value': option.default_value,
                    'required': option.required,
                    'choices': option.choices,
                    'validation_pattern': option.validation_pattern,
                    'category': option.category
                }

                documents.append(json.dumps(option_data))
                ids.append(option.key)

            # Use upsert to add or update all configuration options
            collection.upsert(
                documents=documents,
                ids=ids
            )

            self.logger.info("Configuration registry saved to ChromaDB")

        except ChromaError as e:
            self.logger.error(f"Error saving configuration registry: {e}")
            raise DatabaseConnectionError(f"Failed to save configuration registry: {e}")

    def _load_configurations_to_memory(self) -> None:
        """Load all server configurations into global memory dictionary."""
        try:
            # We need to iterate through all server databases to load configurations
            # First, let's get a list of all configured servers from the global collection
            global_collection = self._get_global_collection("server_list")

            try:
                # Get list of configured servers
                server_results = global_collection.get()
                configured_servers = []

                if server_results['documents']:
                    for doc in server_results['documents']:
                        server_data = json.loads(doc)
                        configured_servers.append(server_data['server_id'])

                # Load configurations for each server
                with self._settings_lock:
                    for server_id in configured_servers:
                        try:
                            server_collection = self._get_collection(server_id, self._config_collection_name)
                            config_results = server_collection.get(ids=[f"config_{server_id}"])

                            if config_results['documents'] and len(config_results['documents']) > 0:
                                config_data = json.loads(config_results['documents'][0])

                                self._global_settings[server_id] = {
                                    'server_name': config_data.get('server_name', ''),
                                    'setup_status': config_data.get('setup_status', 'pending'),
                                    'setup_version': config_data.get('setup_version', '1.0'),
                                    'created_at': config_data.get('created_at', ''),
                                    'updated_at': config_data.get('updated_at', ''),
                                    **config_data.get('configuration_options', {})
                                }
                        except (ChromaError, json.JSONDecodeError) as e:
                            self.logger.warning(f"Error loading configuration for server {server_id}: {e}")
                            continue

                self.logger.info(f"Loaded {len(self._global_settings)} server configurations to memory")

            except ChromaError:
                # Server list collection doesn't exist yet, that's okay
                self.logger.info("No server configurations found to load")

        except ChromaError as e:
            self.logger.error(f"Error loading configurations to memory: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing configuration data: {e}")

    def start_server_setup(self, server_id: str, server_name: str) -> bool:
        """
        Start the one-time setup process for a Discord server.

        Args:
            server_id: Discord server/guild ID
            server_name: Human-readable server name

        Returns:
            True if setup started successfully, False otherwise
        """
        try:
            # Check if server already exists
            if self.get_server_configuration(server_id) is not None:
                self.logger.info(f"Server {server_id} already configured, skipping setup")
                return True

            # Create initial configuration with defaults
            initial_config = {}
            for option in self._configuration_registry.values():
                if option.default_value is not None:
                    initial_config[option.key] = option.default_value

            # Prepare configuration data
            config_data = {
                'server_id': server_id,
                'server_name': server_name,
                'configuration_options': initial_config,
                'setup_status': ConfigurationStatus.PENDING.value,
                'setup_version': '1.0',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            # Save to ChromaDB
            server_collection = self._get_collection(server_id, self._config_collection_name)
            server_collection.add(
                documents=[json.dumps(config_data)],
                ids=[f"config_{server_id}"]
            )

            # Add server to the global server list
            global_collection = self._get_global_collection("server_list")
            server_entry = {
                'server_id': server_id,
                'server_name': server_name,
                'registered_at': datetime.now().isoformat()
            }
            global_collection.upsert(
                documents=[json.dumps(server_entry)],
                ids=[server_id]
            )

            # Update global settings
            with self._settings_lock:
                self._global_settings[server_id] = {
                    'server_name': server_name,
                    'setup_status': ConfigurationStatus.PENDING.value,
                    'setup_version': '1.0',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    **initial_config
                }

            self.logger.info(f"Started setup for server {server_name} ({server_id})")
            return True

        except ChromaError as e:
            self.logger.error(f"Error starting server setup: {e}")
            return False

    def get_server_configuration(self, server_id: str) -> Optional[ServerConfiguration]:
        """
        Get complete configuration for a server.

        Args:
            server_id: Discord server/guild ID

        Returns:
            ServerConfiguration object or None if not found
        """
        try:
            server_collection = self._get_collection(server_id, self._config_collection_name)

            try:
                config_results = server_collection.get(ids=[f"config_{server_id}"])

                if not config_results['documents'] or len(config_results['documents']) == 0:
                    return None

                config_data = json.loads(config_results['documents'][0])

                return ServerConfiguration(
                    server_id=config_data['server_id'],
                    server_name=config_data['server_name'],
                    configuration_options=config_data.get('configuration_options', {}),
                    setup_status=ConfigurationStatus(config_data['setup_status']),
                    created_at=datetime.fromisoformat(config_data['created_at']),
                    updated_at=datetime.fromisoformat(config_data['updated_at']),
                    setup_version=config_data.get('setup_version', '1.0')
                )

            except ChromaError:
                # Collection or document doesn't exist
                return None

        except (ChromaError, json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Error getting server configuration: {e}")
            return None

    def update_server_configuration(
        self,
        server_id: str,
        updates: Dict[str, Any],
        changed_by: str = "system"
    ) -> bool:
        """
        Update server configuration with change tracking.

        Args:
            server_id: Discord server/guild ID
            updates: Dictionary of configuration updates
            changed_by: Who made the changes (user ID or "system")

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get current configuration
            current_config = self.get_server_configuration(server_id)
            if not current_config:
                self.logger.error(f"Server {server_id} not found for configuration update")
                return False

            # Validate updates against registry
            validated_updates = {}
            for key, value in updates.items():
                if key not in self._configuration_registry:
                    self.logger.warning(f"Unknown configuration option: {key}")
                    continue

                option = self._configuration_registry[key]
                if not self._validate_configuration_value(option, value):
                    self.logger.error(f"Invalid value for {key}: {value}")
                    return False

                validated_updates[key] = value

            # Apply updates
            new_config = current_config.configuration_options.copy()
            new_config.update(validated_updates)

            # Prepare updated configuration data
            updated_config_data = {
                'server_id': server_id,
                'server_name': current_config.server_name,
                'configuration_options': new_config,
                'setup_status': current_config.setup_status.value,
                'setup_version': current_config.setup_version,
                'created_at': current_config.created_at.isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            # Save to ChromaDB with change tracking
            server_collection = self._get_collection(server_id, self._config_collection_name)
            server_collection.upsert(
                documents=[json.dumps(updated_config_data)],
                ids=[f"config_{server_id}"]
            )

            # Record changes in history
            history_collection = self._get_collection(server_id, self._history_collection_name)
            for key, new_value in validated_updates.items():
                old_value = current_config.configuration_options.get(key)
                history_entry = {
                    'server_id': server_id,
                    'option_key': key,
                    'old_value': str(old_value),
                    'new_value': str(new_value),
                    'changed_by': changed_by,
                    'changed_at': datetime.now().isoformat()
                }
                history_collection.add(
                    documents=[json.dumps(history_entry)],
                    ids=[f"change_{datetime.now().timestamp()}_{key}"]
                )

            # Update global settings
            with self._settings_lock:
                if server_id in self._global_settings:
                    self._global_settings[server_id].update(validated_updates)
                    self._global_settings[server_id]['updated_at'] = datetime.now().isoformat()

            self.logger.info(f"Updated configuration for server {server_id}: {list(validated_updates.keys())}")
            return True

        except (ChromaError, json.JSONDecodeError) as e:
            self.logger.error(f"Error updating server configuration: {e}")
            return False

    def _validate_configuration_value(self, option: ConfigurationOption, value: Any) -> bool:
        """
        Validate a configuration value against its option definition.

        Args:
            option: Configuration option definition
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Type validation
            if option.data_type == 'boolean':
                if not isinstance(value, bool):
                    return False
            elif option.data_type == 'integer':
                if not isinstance(value, int):
                    return False
            elif option.data_type == 'string':
                if not isinstance(value, str):
                    return False
            elif option.data_type == 'choice':
                if option.choices and value not in option.choices:
                    return False

            # Pattern validation for strings
            if option.validation_pattern and isinstance(value, str):
                import re
                if not re.match(option.validation_pattern, value):
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating configuration value: {e}")
            return False

    def complete_server_setup(self, server_id: str) -> bool:
        """
        Mark server setup as completed.

        Args:
            server_id: Discord server/guild ID

        Returns:
            True if setup completed successfully, False otherwise
        """
        try:
            # Get current configuration
            current_config = self.get_server_configuration(server_id)
            if not current_config:
                self.logger.error(f"Server {server_id} not found for setup completion")
                return False

            # Prepare updated configuration data
            updated_config_data = {
                'server_id': server_id,
                'server_name': current_config.server_name,
                'configuration_options': current_config.configuration_options,
                'setup_status': ConfigurationStatus.COMPLETED.value,
                'setup_version': current_config.setup_version,
                'created_at': current_config.created_at.isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            # Update in ChromaDB
            server_collection = self._get_collection(server_id, self._config_collection_name)
            server_collection.upsert(
                documents=[json.dumps(updated_config_data)],
                ids=[f"config_{server_id}"]
            )

            # Update global settings
            with self._settings_lock:
                if server_id in self._global_settings:
                    self._global_settings[server_id]['setup_status'] = ConfigurationStatus.COMPLETED.value
                    self._global_settings[server_id]['updated_at'] = datetime.now().isoformat()

            self.logger.info(f"Completed setup for server {server_id}")
            return True

        except ChromaError as e:
            self.logger.error(f"Error completing server setup: {e}")
            return False

    @classmethod
    def get_global_setting(cls, server_id: str, key: str, default: Any = None) -> Any:
        """
        Get a setting from the global in-memory settings dictionary.

        Args:
            server_id: Discord server/guild ID
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        with cls._settings_lock:
            server_settings = cls._global_settings.get(server_id, {})
            return server_settings.get(key, default)

    @classmethod
    def get_all_server_settings(cls, server_id: str) -> Dict[str, Any]:
        """
        Get all settings for a server from global dictionary.

        Args:
            server_id: Discord server/guild ID

        Returns:
            Dictionary of all server settings
        """
        with cls._settings_lock:
            return cls._global_settings.get(server_id, {}).copy()

    @classmethod
    def is_server_configured(cls, server_id: str) -> bool:
        """
        Check if a server is properly configured.

        Args:
            server_id: Discord server/guild ID

        Returns:
            True if server is configured, False otherwise
        """
        with cls._settings_lock:
            server_settings = cls._global_settings.get(server_id, {})
            return server_settings.get('setup_status') == ConfigurationStatus.COMPLETED.value

    def add_configuration_option(self, option: ConfigurationOption) -> bool:
        """
        Add a new configuration option to the registry.

        Args:
            option: Configuration option to add

        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Add to in-memory registry
            self._configuration_registry[option.key] = option

            # Prepare option data
            option_data = {
                'key': option.key,
                'display_name': option.display_name,
                'description': option.description,
                'data_type': option.data_type,
                'default_value': option.default_value,
                'required': option.required,
                'choices': option.choices,
                'validation_pattern': option.validation_pattern,
                'category': option.category
            }

            # Save to ChromaDB
            collection = self._get_global_collection(self._registry_collection_name)
            collection.upsert(
                documents=[json.dumps(option_data)],
                ids=[option.key]
            )

            self.logger.info(f"Added configuration option: {option.key}")
            return True

        except ChromaError as e:
            self.logger.error(f"Error adding configuration option: {e}")
            return False

    def get_configuration_options_by_category(self, category: str = None) -> Dict[str, ConfigurationOption]:
        """
        Get configuration options filtered by category.

        Args:
            category: Category to filter by, or None for all options

        Returns:
            Dictionary of configuration options
        """
        if category is None:
            return self._configuration_registry.copy()

        return {
            key: option for key, option in self._configuration_registry.items()
            if option.category == category
        }

    def get_configuration_categories(self) -> List[str]:
        """
        Get list of all configuration categories.

        Returns:
            List of category names
        """
        categories = set(option.category for option in self._configuration_registry.values())
        return sorted(list(categories))

    def health_check(self) -> bool:
        """
        Check if the configuration agent is healthy and ready.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Test ChromaDB connection by accessing the global registry collection
            collection = self._get_global_collection(self._registry_collection_name)
            collection.get(limit=1)  # Try to fetch one document

            # Check if registry is loaded
            if not self._configuration_registry:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    def run_terminal_setup_ui(self, server_id: str, server_name: str) -> bool:
        """
        Run interactive terminal-based configuration UI for server setup.

        Args:
            server_id: Discord server/guild ID
            server_name: Human-readable server name

        Returns:
            True if setup completed successfully, False otherwise
        """
        print(f"\n🚀 Discord Bot Configuration for: {server_name}")
        print("=" * 60)

        # Start server setup if not already started
        if not self.start_server_setup(server_id, server_name):
            print("❌ Failed to initialize server setup")
            return False

        # Group options by category
        categories = self.get_configuration_categories()

        print(f"\nThis setup will configure {len(self._configuration_registry)} options across {len(categories)} categories:")
        for i, category in enumerate(categories, 1):
            options_in_category = len(self.get_configuration_options_by_category(category))
            print(f"  {i}. {category.title()} ({options_in_category} options)")

        print("\nPress Enter to continue with setup, or 'q' to quit...")
        user_input = input().strip().lower()
        if user_input == 'q':
            print("Setup cancelled.")
            return False

        # Configure each category
        all_updates = {}
        for category in categories:
            category_updates = self._configure_category_interactive(category)
            if category_updates is None:  # User cancelled
                print("Setup cancelled.")
                return False
            all_updates.update(category_updates)

        # Apply all updates
        if all_updates:
            print(f"\n📝 Applying {len(all_updates)} configuration changes...")
            if self.update_server_configuration(server_id, all_updates, "terminal_setup"):
                print("✅ Configuration updated successfully!")
            else:
                print("❌ Failed to save configuration")
                return False

        # Complete setup
        if self.complete_server_setup(server_id):
            print("🎉 Server setup completed successfully!")
            self._display_configuration_summary(server_id)
            return True
        else:
            print("❌ Failed to complete setup")
            return False

    def _configure_category_interactive(self, category: str) -> Optional[Dict[str, Any]]:
        """
        Interactively configure options in a specific category.

        Args:
            category: Configuration category to configure

        Returns:
            Dictionary of updates for this category, or None if cancelled
        """
        options = self.get_configuration_options_by_category(category)

        print(f"\n📋 Configuring {category.title()} Settings")
        print("-" * 40)

        updates = {}

        for option in options.values():
            while True:
                print(f"\n🔧 {option.display_name}")
                print(f"   Description: {option.description}")
                print(f"   Type: {option.data_type}")

                if option.default_value is not None:
                    print(f"   Default: {option.default_value}")

                if option.choices:
                    print(f"   Choices: {', '.join(option.choices)}")

                if option.required:
                    print("   ⚠️  Required")
                else:
                    print("   Optional (press Enter to skip)")

                # Get user input
                prompt = f"Enter value for {option.key}"
                if not option.required:
                    prompt += " (or Enter to skip)"
                prompt += ": "

                user_input = input(prompt).strip()

                # Handle empty input
                if not user_input:
                    if option.required:
                        if option.default_value is not None:
                            user_input = str(option.default_value)
                            print(f"Using default value: {user_input}")
                        else:
                            print("❌ This field is required. Please enter a value.")
                            continue
                    else:
                        print("⏭️  Skipping optional field")
                        break

                # Handle special commands
                if user_input.lower() == 'q':
                    return None  # Cancel setup
                elif user_input.lower() == 'help':
                    self._display_option_help(option)
                    continue

                # Convert and validate input
                converted_value = self._convert_user_input(option, user_input)
                if converted_value is None:
                    print(f"❌ Invalid value for {option.data_type}. Please try again.")
                    continue

                if not self._validate_configuration_value(option, converted_value):
                    print("❌ Value failed validation. Please check format and try again.")
                    if option.validation_pattern:
                        print(f"   Expected pattern: {option.validation_pattern}")
                    continue

                # Value accepted
                updates[option.key] = converted_value
                print(f"✅ {option.key} = {converted_value}")
                break

        return updates

    def _convert_user_input(self, option: ConfigurationOption, user_input: str) -> Optional[Any]:
        """
        Convert user input string to appropriate data type.

        Args:
            option: Configuration option definition
            user_input: Raw user input string

        Returns:
            Converted value or None if conversion failed
        """
        try:
            if option.data_type == 'boolean':
                lower_input = user_input.lower()
                if lower_input in ('true', 't', 'yes', 'y', '1', 'on', 'enable', 'enabled'):
                    return True
                elif lower_input in ('false', 'f', 'no', 'n', '0', 'off', 'disable', 'disabled'):
                    return False
                else:
                    return None

            elif option.data_type == 'integer':
                return int(user_input)

            elif option.data_type == 'string' or option.data_type == 'choice':
                return user_input

            else:
                return user_input

        except ValueError:
            return None

    def _display_option_help(self, option: ConfigurationOption) -> None:
        """
        Display detailed help for a configuration option.

        Args:
            option: Configuration option to display help for
        """
        print(f"\n📖 Help for {option.display_name}")
        print(f"Key: {option.key}")
        print(f"Description: {option.description}")
        print(f"Data Type: {option.data_type}")
        print(f"Category: {option.category}")
        print(f"Required: {'Yes' if option.required else 'No'}")

        if option.default_value is not None:
            print(f"Default Value: {option.default_value}")

        if option.choices:
            print(f"Valid Choices: {', '.join(option.choices)}")

        if option.validation_pattern:
            print(f"Validation Pattern: {option.validation_pattern}")

        # Provide examples based on data type
        if option.data_type == 'boolean':
            print("Examples: true, false, yes, no, 1, 0")
        elif option.data_type == 'integer':
            print("Examples: 42, 100, -1")
        elif option.key.endswith('_channel') or option.key.endswith('_channels'):
            print("Example: 123456789012345678 (Discord channel ID)")
        elif option.key.endswith('_roles'):
            print("Example: 123456789012345678,987654321098765432 (comma-separated role IDs)")

    def _display_configuration_summary(self, server_id: str) -> None:
        """
        Display a summary of the server's current configuration.

        Args:
            server_id: Discord server/guild ID
        """
        config = self.get_server_configuration(server_id)
        if not config:
            print("❌ Unable to retrieve configuration summary")
            return

        print(f"\n📊 Configuration Summary for {config.server_name}")
        print("=" * 60)

        # Group by category
        categories = self.get_configuration_categories()

        for category in categories:
            options = self.get_configuration_options_by_category(category)
            print(f"\n📁 {category.title()}")
            print("-" * 30)

            for option_key, option in options.items():
                value = config.configuration_options.get(option_key, "Not set")
                status = "✅" if option_key in config.configuration_options else "⚪"
                print(f"   {status} {option.display_name}: {value}")

        print(f"\nSetup Status: {config.setup_status.value}")
        print(f"Version: {config.setup_version}")
        print(f"Last Updated: {config.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

    def display_server_configuration(self, server_id: str) -> bool:
        """
        Display current configuration for a server in a readable format.

        Args:
            server_id: Discord server/guild ID

        Returns:
            True if displayed successfully, False otherwise
        """
        config = self.get_server_configuration(server_id)
        if not config:
            print(f"❌ No configuration found for server {server_id}")
            return False

        self._display_configuration_summary(server_id)
        return True

    def run_configuration_wizard(self, server_id: str = None) -> bool:
        """
        Run a comprehensive configuration wizard.

        Args:
            server_id: Specific server to configure, or None for interactive selection

        Returns:
            True if wizard completed successfully, False otherwise
        """
        print("\n🧙 Discord Bot Configuration Wizard")
        print("=" * 50)

        # Server selection if not provided
        if server_id is None:
            server_id = self._interactive_server_selection()
            if not server_id:
                return False

        # Get server configuration
        config = self.get_server_configuration(server_id)
        if not config:
            print("❌ Server not found. Please run initial setup first.")
            return False

        while True:
            print(f"\n🏠 Server: {config.server_name}")
            print("Choose an action:")
            print("1. View current configuration")
            print("2. Modify configuration")
            print("3. Add new configuration option")
            print("4. Reset to defaults")
            print("5. Export configuration")
            print("6. Import configuration")
            print("0. Exit wizard")

            choice = input("\nEnter your choice (0-6): ").strip()

            if choice == '0':
                print("Wizard completed.")
                return True
            elif choice == '1':
                self.display_server_configuration(server_id)
            elif choice == '2':
                self._modify_configuration_interactive(server_id)
            elif choice == '3':
                self._add_option_interactive()
            elif choice == '4':
                self._reset_configuration_interactive(server_id)
            elif choice == '5':
                self._export_configuration_interactive(server_id)
            elif choice == '6':
                self._import_configuration_interactive(server_id)
            else:
                print("❌ Invalid choice. Please try again.")

    def _interactive_server_selection(self) -> Optional[str]:
        """
        Interactive server selection for configuration wizard.

        Returns:
            Selected server ID or None if cancelled
        """
        print("\n🏢 Available Servers:")

        servers = []
        try:
            # Get list of configured servers from the global collection
            global_collection = self._get_global_collection("server_list")
            server_results = global_collection.get()

            if server_results['documents']:
                for doc in server_results['documents']:
                    server_data = json.loads(doc)
                    server_id = server_data['server_id']

                    # Get the configuration status for each server
                    try:
                        config = self.get_server_configuration(server_id)
                        if config:
                            servers.append((server_id, config.server_name, config.setup_status.value))
                    except Exception:
                        # If we can't get the config, still show the server
                        servers.append((server_id, server_data.get('server_name', server_id), 'unknown'))

        except ChromaError:
            # No server list collection exists yet
            pass

        if not servers:
            print("No servers configured. Please run initial setup first.")
            return None

        for i, (server_id, server_name, status) in enumerate(servers, 1):
            status_icon = "✅" if status == "completed" else "⚠️"
            print(f"  {i}. {status_icon} {server_name} ({server_id})")

        while True:
            try:
                choice = input(f"\nSelect server (1-{len(servers)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return None

                index = int(choice) - 1
                if 0 <= index < len(servers):
                    return servers[index][0]  # Return server_id
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a number or 'q' to quit.")

    def _modify_configuration_interactive(self, server_id: str) -> None:
        """
        Interactive configuration modification.

        Args:
            server_id: Discord server/guild ID
        """
        # Implementation would allow selecting and modifying individual options
        # This is a placeholder for the interactive modification interface
        print("🔧 Configuration modification interface would be implemented here")

    def _add_option_interactive(self) -> None:
        """Interactive addition of new configuration options."""
        print("➕ Add new configuration option interface would be implemented here")

    def _reset_configuration_interactive(self, server_id: str) -> None:
        """Interactive configuration reset."""
        print("🔄 Configuration reset interface would be implemented here")

    def _export_configuration_interactive(self, server_id: str) -> None:
        """Interactive configuration export."""
        print("📤 Configuration export interface would be implemented here")

    def _import_configuration_interactive(self, server_id: str) -> None:
        """Interactive configuration import."""
        print("📥 Configuration import interface would be implemented here")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get configuration agent statistics.

        Returns:
            Dictionary containing agent statistics
        """
        try:
            # Count total servers
            total_servers = 0
            status_counts = {}

            try:
                global_collection = self._get_global_collection("server_list")
                server_results = global_collection.get()

                if server_results['documents']:
                    total_servers = len(server_results['documents'])

                    # Count servers by status
                    for doc in server_results['documents']:
                        server_data = json.loads(doc)
                        server_id = server_data['server_id']

                        try:
                            config = self.get_server_configuration(server_id)
                            if config:
                                status = config.setup_status.value
                                status_counts[status] = status_counts.get(status, 0) + 1
                        except Exception:
                            status_counts['unknown'] = status_counts.get('unknown', 0) + 1

            except ChromaError:
                # No server list collection exists yet
                pass

            # Count configuration options
            total_options = len(self._configuration_registry)

            return {
                "total_servers": total_servers,
                "status_counts": status_counts,
                "total_configuration_options": total_options,
                "categories": self.get_configuration_categories(),
                "global_settings_loaded": len(self._global_settings),
                "storage_type": "ChromaDB",
                "healthy": self.health_check()
            }

        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


def get_configuration_agent() -> ConfigurationAgent:
    """
    Get singleton instance of ConfigurationAgent.

    Returns:
        ConfigurationAgent instance
    """
    if not hasattr(get_configuration_agent, '_instance'):
        get_configuration_agent._instance = ConfigurationAgent()

    return get_configuration_agent._instance