#!/usr/bin/env python3
"""Discord Bot Initial Setup Script

This script provides a terminal-based UI for configuring the Discord bot
during the initial setup process. It walks through configuration options
sequentially, validates responses, and stores settings in ChromaDB.

Usage:
    python setup_bot.py
"""

import sys
import os
import logging
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from src.setup.configuration_manager import ConfigurationManager, get_configuration_manager
from src.db.setup_db import initialize_db


def setup_logging():
    """Setup logging for the setup script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('setup.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def print_banner():
    """Print setup banner."""
    print("\n" + "=" * 70)
    print("🤖  DISCORD INDEXER BOT - QUICK SETUP")
    print("=" * 70)
    print("Quick setup to configure essential bot behavior.")
    print("The bot will index Discord messages and provide AI-powered search.")
    print("=" * 70)


def get_server_info():
    """Get server information from user."""
    print("\n📋 SERVER INFORMATION")
    print("-" * 30)

    while True:
        server_id = input("Enter your Discord Server ID: ").strip()
        if server_id and server_id.isdigit() and len(server_id) >= 17:
            break
        print("❌ Please enter a valid Discord Server ID (17+ digit number)")

    while True:
        server_name = input("Enter your Discord Server Name: ").strip()
        if server_name:
            break
        print("❌ Please enter a valid server name")

    return server_id, server_name


def confirm_setup_start(server_name: str):
    """Confirm setup start with the user."""
    print(f"\n📝 QUICK SETUP")
    print("-" * 30)
    print(f"Server: {server_name}")
    print("\nThis setup will ask you one essential question about error handling.")
    print("You can:")
    print("  • Press Enter to use the default (recommended)")
    print("  • Type 'help' for detailed information")
    print("  • Type 'q' to quit setup")

    while True:
        response = input("\nReady to start setup? [Y/n]: ").strip().lower()
        if response in ('', 'y', 'yes'):
            return True
        elif response in ('n', 'no', 'q'):
            return False
        print("❌ Please enter 'y' or 'n'")


def run_simple_setup(agent: ConfigurationManager, server_id: str, server_name: str):
    """Run the simplified configuration setup."""
    print(f"\n🚀 Configuring {server_name}")
    print("=" * 50)

    # Start server setup
    if not manager.start_server_setup(server_id, server_name):
        print("❌ Failed to initialize server setup")
        return False

    # Get the single configuration option
    option = manager._configuration_registry['message_processing_error_handling']

    print(f"\n🔧 ESSENTIAL CONFIGURATION")
    print("-" * 40)
    print(f"Setting: {option.display_name}")
    print(f"Description: {option.description}")
    print(f"Choices: {', '.join(option.choices)}")
    print(f"Default: {option.default_value} (recommended)")
    print("\nExplanation:")
    print("  • 'skip' = Continue processing other messages if one fails")
    print("  • 'stop' = Stop all processing when any message fails")

    # Get user input
    while True:
        user_input = input(f"\nEnter choice [default: {option.default_value}]: ").strip()

        # Handle special commands
        if user_input.lower() == 'q':
            print("\n❌ Setup cancelled by user")
            return False
        elif user_input.lower() == 'help':
            print("\n📖 DETAILED HELP")
            print("=" * 40)
            print("When the bot processes Discord messages for indexing, sometimes")
            print("errors can occur (network issues, corrupted messages, etc.).")
            print("")
            print("• SKIP (recommended): If one message fails, continue with others")
            print("  - Pro: More resilient, indexes as much as possible")
            print("  - Con: Some messages might be missed")
            print("")
            print("• STOP: If any message fails, stop the entire process")
            print("  - Pro: Ensures no data is missed")
            print("  - Con: Entire batch fails if one message has issues")
            print("=" * 40)
            continue

        # Handle empty input (use default)
        if not user_input:
            user_input = option.default_value
            print(f"✅ Using default: {user_input}")

        # Validate input
        if user_input.lower() in ['skip', 'stop']:
            chosen_value = user_input.lower()
            break
        else:
            print("❌ Please enter 'skip' or 'stop'")
            continue

    # Apply the configuration
    updates = {option.key: chosen_value}

    print(f"\n💾 SAVING CONFIGURATION")
    print("=" * 40)

    if manager.update_server_configuration(server_id, updates, "initial_setup"):
        print("✅ Configuration saved successfully!")
    else:
        print("❌ Failed to save configuration")
        return False

    # Complete setup
    if manager.complete_server_setup(server_id):
        print(f"\n🎉 SETUP COMPLETED!")
        print("=" * 40)
        print(f"Server: {server_name}")
        print(f"Error Handling: {chosen_value}")
        print(f"Status: Ready to use")
        print("\nYour bot is now configured and ready to start!")
        print("Run 'python main.py' to start the bot.")
        return True
    else:
        print("❌ Failed to complete setup")
        return False


def _display_detailed_help(option):
    """Display detailed help for a configuration option."""
    print(f"\n📖 DETAILED HELP: {option.display_name}")
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

    # Provide specific examples based on the option key
    print("\n💡 Examples:")
    if option.key.endswith('_channel'):
        print("  Discord Channel ID: 123456789012345678")
        print("  (Right-click channel → Copy ID)")
    elif option.key.endswith('_roles'):
        print("  Single role: 123456789012345678")
        print("  Multiple roles: 123456789012345678,987654321098765432")
        print("  (Right-click role → Copy ID)")
    elif option.data_type == 'boolean':
        print("  True values: true, yes, y, 1, on, enable")
        print("  False values: false, no, n, 0, off, disable")
    elif option.data_type == 'integer':
        print("  Whole numbers: 5, 10, 100")
    elif option.key == 'message_processing_error_handling':
        print("  skip: Continue processing other messages when one fails")
        print("  stop: Stop all processing when any message fails")

    print("=" * 50)


def _display_setup_summary(agent: ConfigurationManager, server_id: str):
    """Display setup completion summary."""
    config = manager.get_server_configuration(server_id)
    if not config:
        print("❌ Unable to retrieve configuration summary")
        return

    print(f"Server: {config.server_name}")
    print(f"Setup Status: {config.setup_status.value}")
    print(f"Configuration Version: {config.setup_version}")
    print(f"Total Settings: {len(config.configuration_options)}")

    # Show configured options by category
    categories = manager.get_configuration_categories()
    configured_count = 0

    for category in categories:
        options = manager.get_configuration_options_by_category(category)
        category_configured = sum(1 for key in options.keys() if key in config.configuration_options)
        configured_count += category_configured
        print(f"  {category.title()}: {category_configured}/{len(options)} configured")

    print(f"\nNext Steps:")
    print("• Start your Discord bot with: python -m src.main")
    print("• Use 'python change_settings.py' to modify settings later")
    print("• Check setup.log for detailed setup information")


def main():
    """Main setup function."""
    logger = setup_logging()

    try:
        print_banner()

        # Initialize database
        print("\n🗄️ Initializing database...")
        initialize_db()

        # Initialize configuration agent
        print("🤖 Initializing configuration manager...")
        manager = get_configuration_manager()

        # Health check
        if not manager.health_check():
            print("❌ Configuration agent health check failed")
            sys.exit(1)

        # Get server information
        server_id, server_name = get_server_info()

        # Check if server already configured
        existing_config = manager.get_server_configuration(server_id)
        if existing_config and manager.is_server_configured(server_id):
            print(f"\n⚠️ Server '{server_name}' is already configured!")
            print("Use 'python change_settings.py' to modify existing settings.")

            while True:
                response = input("Reconfigure anyway? [y/N]: ").strip().lower()
                if response in ('', 'n', 'no'):
                    print("Setup cancelled.")
                    sys.exit(0)
                elif response in ('y', 'yes'):
                    break
                print("❌ Please enter 'y' or 'n'")

        # Show setup overview
        if not confirm_setup_start(server_name):
            print("Setup cancelled.")
            sys.exit(0)

        # Run setup
        success = run_simple_setup(agent, server_id, server_name)

        if success:
            print("\n✅ Discord bot setup completed successfully!")
            print("You can now start your bot.")
        else:
            print("\n❌ Setup failed. Check setup.log for details.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Setup failed with error: {e}")
        print(f"\n❌ Setup failed: {e}")
        print("Check setup.log for detailed error information.")
        sys.exit(1)


if __name__ == "__main__":
    main()