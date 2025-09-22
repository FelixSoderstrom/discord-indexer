#!/usr/bin/env python3
"""Discord Bot Settings Management Script

This script provides a terminal-based UI for modifying existing Discord bot
configuration settings. It allows users to reconfigure individual options,
export/import configurations, and manage multiple servers.

Usage:
    python change_settings.py [server_id]
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.setup.configuration_manager import ConfigurationManager, get_configuration_manager, ConfigurationOption
from src.db.setup_db import initialize_db


def setup_logging():
    """Setup logging for the settings script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('settings_change.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def print_banner():
    """Print settings management banner."""
    print("\n" + "=" * 70)
    print("🔧  DISCORD INDEXER BOT - SETTINGS MANAGEMENT")
    print("=" * 70)
    print("Modify, export, and manage your Discord bot configuration.")
    print("=" * 70)


def select_server(agent: ConfigurationManager, provided_server_id: Optional[str] = None) -> Optional[str]:
    """Select a server to configure."""
    if provided_server_id:
        # Validate provided server ID
        config = manager.get_server_configuration(provided_server_id)
        if config:
            print(f"📋 Selected server: {config.server_name} ({provided_server_id})")
            return provided_server_id
        else:
            print(f"❌ Server {provided_server_id} not found.")
            print("Available servers:")

    # Show available servers
    stats = manager.get_stats()
    if stats["total_servers"] == 0:
        print("❌ No servers configured. Run 'python setup_bot.py' first.")
        return None

    return manager._interactive_server_selection()


def show_main_menu():
    """Display the main menu options."""
    print("\n🏠 MAIN MENU")
    print("=" * 30)
    print("1. View current configuration")
    print("2. Modify individual settings")
    print("3. Modify settings by category")
    print("4. Export configuration")
    print("5. Import configuration")
    print("6. Reset to defaults")
    print("7. Add new configuration option")
    print("8. Server statistics")
    print("9. Switch server")
    print("0. Exit")


def view_configuration(agent: ConfigurationManager, server_id: str):
    """Display current server configuration."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration")
        return

    print(f"\n📊 CONFIGURATION: {config.server_name}")
    print("=" * 60)

    # Group by category
    categories = manager.get_configuration_categories()

    for category in categories:
        options = manager.get_configuration_options_by_category(category)
        print(f"\n📁 {category.upper()}")
        print("-" * 40)

        for option_key, option in options.items():
            value = config.configuration_options.get(option_key, "Not set")
            status = "✅" if option_key in config.configuration_options else "⚪"

            # Format value display
            if isinstance(value, bool):
                value_display = "Yes" if value else "No"
            else:
                value_display = str(value)

            print(f"   {status} {option.display_name}: {value_display}")

    print(f"\n📈 METADATA")
    print("-" * 40)
    print(f"   Setup Status: {config.setup_status.value}")
    print(f"   Version: {config.setup_version}")
    print(f"   Created: {config.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Updated: {config.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")


def modify_individual_settings(agent: ConfigurationManager, server_id: str):
    """Modify individual configuration settings."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration")
        return

    print(f"\n🔧 MODIFY SETTINGS: {config.server_name}")
    print("=" * 50)

    # Show all options with current values
    all_options = manager._configuration_registry
    options_list = list(all_options.items())

    print("Available settings:")
    for i, (key, option) in enumerate(options_list, 1):
        current_value = config.configuration_options.get(key, "Not set")
        status = "✅" if key in config.configuration_options else "⚪"
        print(f"  {i:2d}. {status} {option.display_name}: {current_value}")

    while True:
        try:
            choice = input(f"\nSelect setting to modify (1-{len(options_list)}) or 'q' to return: ").strip()
            if choice.lower() == 'q':
                return

            index = int(choice) - 1
            if 0 <= index < len(options_list):
                option_key, option = options_list[index]
                _modify_single_option(agent, server_id, option_key, option, config)

                # Refresh config after modification
                config = manager.get_server_configuration(server_id)
                if not config:
                    print("❌ Unable to refresh configuration")
                    return
            else:
                print("❌ Invalid selection")

        except ValueError:
            print("❌ Please enter a number or 'q'")


def modify_category_settings(agent: ConfigurationManager, server_id: str):
    """Modify settings by category."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration")
        return

    print(f"\n📂 MODIFY BY CATEGORY: {config.server_name}")
    print("=" * 50)

    categories = manager.get_configuration_categories()
    print("Available categories:")
    for i, category in enumerate(categories, 1):
        options_in_category = manager.get_configuration_options_by_category(category)
        configured_count = sum(1 for key in options_in_category.keys() if key in config.configuration_options)
        print(f"  {i}. {category.title()} ({configured_count}/{len(options_in_category)} configured)")

    while True:
        try:
            choice = input(f"\nSelect category (1-{len(categories)}) or 'q' to return: ").strip()
            if choice.lower() == 'q':
                return

            index = int(choice) - 1
            if 0 <= index < len(categories):
                category = categories[index]
                _modify_category_options(agent, server_id, category, config)

                # Refresh config after modification
                config = manager.get_server_configuration(server_id)
                if not config:
                    print("❌ Unable to refresh configuration")
                    return
            else:
                print("❌ Invalid selection")

        except ValueError:
            print("❌ Please enter a number or 'q'")


def _modify_single_option(agent: ConfigurationManager, server_id: str, option_key: str, option: ConfigurationOption, config):
    """Modify a single configuration option."""
    current_value = config.configuration_options.get(option_key, "Not set")

    print(f"\n🔧 MODIFY: {option.display_name}")
    print("=" * 50)
    print(f"Description: {option.description}")
    print(f"Current value: {current_value}")
    print(f"Data type: {option.data_type}")

    if option.choices:
        print(f"Valid choices: {', '.join(option.choices)}")

    if option.default_value is not None:
        print(f"Default: {option.default_value}")

    print("\nEnter new value (or 'q' to cancel, 'help' for details):")

    while True:
        user_input = input("> ").strip()

        if user_input.lower() == 'q':
            print("Modification cancelled")
            return

        if user_input.lower() == 'help':
            _display_option_help(option)
            continue

        # Convert and validate input
        converted_value = manager._convert_user_input(option, user_input)
        if converted_value is None:
            print(f"❌ Invalid value for {option.data_type}. Please try again.")
            continue

        if not manager._validate_configuration_value(option, converted_value):
            print("❌ Value failed validation. Please check format and try again.")
            if option.validation_pattern:
                print(f"   Expected pattern: {option.validation_pattern}")
            if option.choices:
                print(f"   Valid choices: {', '.join(option.choices)}")
            continue

        # Apply the change
        updates = {option_key: converted_value}
        if manager.update_server_configuration(server_id, updates, "manual_change"):
            print(f"✅ Updated {option.display_name} = {converted_value}")
        else:
            print("❌ Failed to save changes")
        return


def _modify_category_options(agent: ConfigurationManager, server_id: str, category: str, config):
    """Modify all options in a category."""
    options = manager.get_configuration_options_by_category(category)

    print(f"\n📂 CATEGORY: {category.upper()}")
    print("=" * 50)

    updates = {}

    for option_key, option in options.items():
        current_value = config.configuration_options.get(option_key, "Not set")

        print(f"\n🔧 {option.display_name}")
        print(f"   Description: {option.description}")
        print(f"   Current: {current_value}")

        if option.choices:
            print(f"   Choices: {', '.join(option.choices)}")

        prompt = "   New value (Enter to keep current, 'q' to finish category): "
        user_input = input(prompt).strip()

        if user_input.lower() == 'q':
            break

        if not user_input:  # Keep current value
            print("   ⏭️ Keeping current value")
            continue

        # Convert and validate input
        converted_value = manager._convert_user_input(option, user_input)
        if converted_value is None:
            print(f"   ❌ Invalid value for {option.data_type}. Keeping current value.")
            continue

        if not manager._validate_configuration_value(option, converted_value):
            print("   ❌ Value failed validation. Keeping current value.")
            continue

        updates[option_key] = converted_value
        print(f"   ✅ Will update to: {converted_value}")

    # Apply all updates for this category
    if updates:
        print(f"\n💾 Applying {len(updates)} changes...")
        if manager.update_server_configuration(server_id, updates, "category_change"):
            print("✅ Category updates saved successfully!")
        else:
            print("❌ Failed to save category updates")
    else:
        print("No changes made to this category.")


def export_configuration(agent: ConfigurationManager, server_id: str):
    """Export server configuration to a JSON file."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration")
        return

    # Prepare export data
    export_data = {
        "export_info": {
            "server_id": server_id,
            "server_name": config.server_name,
            "exported_at": config.updated_at.isoformat(),
            "setup_version": config.setup_version
        },
        "configuration": config.configuration_options
    }

    # Generate filename
    safe_server_name = "".join(c for c in config.server_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    filename = f"config_{safe_server_name}_{server_id}.json"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Configuration exported to: {filename}")
        print(f"   Server: {config.server_name}")
        print(f"   Settings: {len(config.configuration_options)}")

    except (IOError, OSError) as e:
        print(f"❌ Failed to export configuration: {e}")


def import_configuration(agent: ConfigurationManager, server_id: str):
    """Import server configuration from a JSON file."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve current configuration")
        return

    filename = input("Enter configuration file path: ").strip()
    if not filename:
        print("Import cancelled")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            import_data = json.load(f)

        # Validate import data structure
        if "configuration" not in import_data:
            print("❌ Invalid configuration file format")
            return

        imported_config = import_data["configuration"]
        print(f"\n📥 IMPORT PREVIEW")
        print("=" * 40)

        if "export_info" in import_data:
            info = import_data["export_info"]
            print(f"Source server: {info.get('server_name', 'Unknown')}")
            print(f"Export date: {info.get('exported_at', 'Unknown')}")

        print(f"Settings to import: {len(imported_config)}")

        # Show what will be changed
        changes = {}
        for key, value in imported_config.items():
            if key in manager._configuration_registry:
                current = config.configuration_options.get(key, "Not set")
                if current != value:
                    changes[key] = {"old": current, "new": value}

        if changes:
            print(f"Changes to be made: {len(changes)}")
            for key, change in changes.items():
                option = manager._configuration_registry[key]
                print(f"  • {option.display_name}: {change['old']} → {change['new']}")
        else:
            print("No changes needed - all settings match current configuration")

        # Confirm import
        confirm = input("\nProceed with import? [y/N]: ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("Import cancelled")
            return

        # Apply import
        valid_updates = {}
        for key, value in imported_config.items():
            if key in manager._configuration_registry:
                option = manager._configuration_registry[key]
                if manager._validate_configuration_value(option, value):
                    valid_updates[key] = value
                else:
                    print(f"⚠️ Skipping invalid value for {option.display_name}")

        if valid_updates:
            if manager.update_server_configuration(server_id, valid_updates, "config_import"):
                print(f"✅ Successfully imported {len(valid_updates)} settings!")
            else:
                print("❌ Failed to import configuration")
        else:
            print("❌ No valid settings to import")

    except (FileNotFoundError, IOError):
        print(f"❌ Configuration file not found: {filename}")
    except json.JSONDecodeError:
        print("❌ Invalid JSON format in configuration file")
    except Exception as e:
        print(f"❌ Import failed: {e}")


def reset_to_defaults(agent: ConfigurationManager, server_id: str):
    """Reset server configuration to default values."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration")
        return

    print(f"\n🔄 RESET TO DEFAULTS: {config.server_name}")
    print("=" * 50)
    print("This will reset ALL settings to their default values.")
    print("Current custom settings will be lost.")

    confirm = input("\nAre you sure you want to reset? Type 'RESET' to confirm: ").strip()
    if confirm != 'RESET':
        print("Reset cancelled")
        return

    # Prepare default values
    default_updates = {}
    for option in manager._configuration_registry.values():
        if option.default_value is not None:
            default_updates[option.key] = option.default_value

    if default_updates:
        if manager.update_server_configuration(server_id, default_updates, "reset_defaults"):
            print(f"✅ Successfully reset {len(default_updates)} settings to defaults!")
        else:
            print("❌ Failed to reset configuration")
    else:
        print("⚠️ No default values available to reset to")


def show_server_statistics(agent: ConfigurationManager, server_id: str):
    """Display server configuration statistics."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration")
        return

    stats = manager.get_stats()

    print(f"\n📊 SERVER STATISTICS: {config.server_name}")
    print("=" * 60)
    print(f"Server ID: {server_id}")
    print(f"Setup Status: {config.setup_status.value}")
    print(f"Configuration Version: {config.setup_version}")
    print(f"Total Options Available: {stats['total_configuration_options']}")
    print(f"Options Configured: {len(config.configuration_options)}")
    print(f"Configuration Completeness: {len(config.configuration_options)/stats['total_configuration_options']*100:.1f}%")

    # Category breakdown
    categories = manager.get_configuration_categories()
    print(f"\n📂 CATEGORY BREAKDOWN")
    print("-" * 40)
    for category in categories:
        options = manager.get_configuration_options_by_category(category)
        configured = sum(1 for key in options.keys() if key in config.configuration_options)
        percentage = configured / len(options) * 100 if options else 0
        print(f"  {category.title()}: {configured}/{len(options)} ({percentage:.1f}%)")

    print(f"\n🕒 TIMESTAMPS")
    print("-" * 40)
    print(f"Created: {config.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Last Updated: {config.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")


def _display_option_help(option: ConfigurationOption):
    """Display detailed help for a configuration option."""
    print(f"\n📖 HELP: {option.display_name}")
    print("=" * 50)
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

    print("=" * 50)


def main():
    """Main settings management function."""
    logger = setup_logging()

    try:
        print_banner()

        # Get server ID from command line if provided
        provided_server_id = sys.argv[1] if len(sys.argv) > 1 else None

        # Initialize database and agent
        print("🗄️ Initializing database...")
        initialize_db()

        print("🤖 Initializing configuration manager...")
        manager = get_configuration_manager()

        if not manager.health_check():
            print("❌ Configuration agent health check failed")
            sys.exit(1)

        # Select server
        server_id = select_server(agent, provided_server_id)
        if not server_id:
            sys.exit(1)

        # Main interaction loop
        while True:
            show_main_menu()

            try:
                choice = input("\nEnter your choice (0-9): ").strip()

                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '1':
                    view_configuration(agent, server_id)
                elif choice == '2':
                    modify_individual_settings(agent, server_id)
                elif choice == '3':
                    modify_category_settings(agent, server_id)
                elif choice == '4':
                    export_configuration(agent, server_id)
                elif choice == '5':
                    import_configuration(agent, server_id)
                elif choice == '6':
                    reset_to_defaults(agent, server_id)
                elif choice == '7':
                    print("➕ Adding new configuration options requires code changes.")
                    print("   Contact the bot administrator.")
                elif choice == '8':
                    show_server_statistics(agent, server_id)
                elif choice == '9':
                    new_server_id = select_server(agent)
                    if new_server_id:
                        server_id = new_server_id
                else:
                    print("❌ Invalid choice. Please try again.")

                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break

    except KeyboardInterrupt:
        print("\n\n❌ Settings management interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Settings management failed with error: {e}")
        print(f"\n❌ Settings management failed: {e}")
        print("Check settings_change.log for detailed error information.")
        sys.exit(1)


if __name__ == "__main__":
    main()