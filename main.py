import asyncio
import logging
import os
from typing import NoReturn
from datetime import datetime
import discord
from src.config.settings import settings
from src.bot.client import DiscordBot
from src.bot.actions import setup_bot_actions
from src.db import initialize_db
from src.llm.agents.configuration_agent import get_configuration_agent
from chromadb.errors import ChromaError


async def main() -> None:
    """Main execution flow - orchestrates the Discord bot.

    Sets up logging, creates bot instance, configures event handlers,
    and starts the Discord connection with proper error handling.
    """
    logger = logging.getLogger(__name__)

    # Setup logging with file output
    log_level = logging.INFO if settings.DEBUG else logging.WARNING
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Configure logging with file and console output
    log_filename = f"discord-indexer-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    logger.info(f"Logging to file: {log_filepath}")

    logger.info("🚀 Starting Discord Indexer Bot...")

    try:
        # Initialize database
        logger.info("🗄️ Initializing database...")
        initialize_db()

        # Initialize configuration agent and check setup
        logger.info("⚙️ Checking bot configuration...")
        config_agent = get_configuration_agent()

        if not config_agent.health_check():
            logger.error("❌ Configuration agent health check failed")
            print("\n❌ Configuration system is not healthy.")
            print("Please run 'python setup_bot.py' to configure the bot.")
            return

        # Check if any servers are configured
        stats = config_agent.get_stats()
        if stats["total_servers"] == 0:
            logger.warning("⚠️ No servers configured")
            print("\n⚠️ No Discord servers are configured for this bot.")
            print("Please run 'python setup_bot.py' to configure your server.")
            return

        # Load configuration settings into memory
        logger.info(f"📋 Loaded configuration for {stats['total_servers']} server(s)")
        completed_servers = stats["status_counts"].get("completed", 0)

        if completed_servers == 0:
            logger.warning("⚠️ No servers have completed setup")
            print("\n⚠️ No servers have completed the setup process.")
            print("Please run 'python setup_bot.py' to complete server configuration.")
            return

        logger.info(f"✅ {completed_servers} server(s) configured and ready")

        # Create bot instance
        logger.info("🤖 Creating bot instance...")
        bot = DiscordBot()

        # Setup actions and event handlers
        logger.info("⚙️ Setting up event handlers...")
        setup_bot_actions(bot)

        # Start bot with token
        logger.info("🔐 Connecting to Discord...")
        await bot.start(settings.DISCORD_TOKEN)

    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except (discord.LoginFailure, discord.HTTPException, discord.ConnectionClosed, 
            ValueError, OSError, RuntimeError, ChromaError) as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    print("=" * 50)
    print("Discord Message Indexer Bot")
    print("Building foundation for AI-powered search")
    print("=" * 50)

    asyncio.run(main())
