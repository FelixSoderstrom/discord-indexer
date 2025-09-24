import asyncio
import logging
import os
import sys
from typing import NoReturn
from datetime import datetime
import discord

# Fix Windows console encoding for emoji support
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())
from src.config.settings import settings
from src.bot.client import DiscordBot
from src.bot.actions import setup_bot_actions
from src.db import initialize_db
from src.setup import load_configured_servers
from src.cleanup import Cleanup
from src.ai.model_manager import ModelManager
from chromadb.errors import ChromaError


async def main() -> None:
    """Main execution flow - orchestrates the Discord bot.

    Sets up logging, creates bot instance, configures event handlers,
    and starts the Discord connection with proper error handling and cleanup.
    """
    logger = logging.getLogger(__name__)
    cleanup_manager = None
    bot = None

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
        # Initialize database and configuration tables
        logger.info("🗄️ Initializing database and configuration tables...")
        initialize_db()

        # Load configured servers into memory cache
        logger.info("📋 Loading server configurations...")
        configured_servers = load_configured_servers()
        
        if len(configured_servers) == 0:
            logger.info("⚠️ No servers configured yet - will configure as messages arrive")
            print("\n⚠️ No Discord servers are pre-configured.")
            print("The bot will automatically prompt for configuration when messages arrive from new servers.")
        else:
            logger.info(f"✅ {len(configured_servers)} server(s) already configured and ready")

        # Preload embedding models to prevent runtime blocking
        logger.info("🔤 Preloading embedding models...")
        try:
            from src.db.embedders import preload_embedder
            await preload_embedder("BAAI/bge-large-en-v1.5")
            logger.info("✅ BGE embedding model preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload BGE embedding model: {e}")
            logger.info("BGE model will be loaded on first use (may cause delays)")

        # Initialize ModelManager and load both models
        logger.info("🧠 Initializing ModelManager...")
        model_manager = ModelManager()
        
        # Health check both models
        logger.info("🔍 Performing health checks on both models...")
        health_results = model_manager.health_check_both_models()
        
        if health_results['both_healthy']:
            logger.info(f"✅ Both models loaded and healthy - "
                       f"text:{health_results['text_model']['response_time']:.2f}s, "
                       f"vision:{health_results['vision_model']['response_time']:.2f}s")
        else:
            error_msg = "Model health check failed: "
            if not health_results['text_model']['healthy']:
                error_msg += f"Text model error: {health_results['text_model']['error']}. "
            if not health_results['vision_model']['healthy']:
                error_msg += f"Vision model error: {health_results['vision_model']['error']}. "
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Create bot instance
        logger.info("🤖 Creating bot instance...")
        bot = DiscordBot()

        # Initialize cleanup manager with bot reference
        cleanup_manager = Cleanup(bot)
        logger.info("🧹 Cleanup manager initialized")

        # Setup actions and event handlers
        logger.info("⚙️ Setting up event handlers...")
        setup_bot_actions(bot)

        # Start bot with token
        logger.info("🔐 Connecting to Discord...")
        await bot.start(settings.DISCORD_TOKEN)

    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except (discord.LoginFailure, discord.HTTPException, discord.ConnectionClosed,
            ValueError, OSError, RuntimeError, ChromaError, ConnectionError, TimeoutError, KeyError) as e:
        logger.error(f"Failed to start bot: {e}")
        raise
    finally:
        # Always run cleanup, regardless of how the bot stopped
        if cleanup_manager and bot:
            logger.info("🧹 Initiating bot cleanup...")
            try:
                await cleanup_manager.cleanup_all()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
                # Log error but don't raise - we're shutting down anyway
        elif bot and not cleanup_manager:
            # Fallback cleanup if cleanup_manager wasn't created
            logger.info("🧹 Performing fallback bot cleanup...")
            try:
                if not bot.is_closed():
                    await bot.close()
                    logger.info("Bot connection closed during fallback cleanup")
            except Exception as fallback_error:
                logger.error(f"Error during fallback cleanup: {fallback_error}")

        logger.info("🔚 Bot shutdown sequence completed")


if __name__ == "__main__":
    print("=" * 50)
    print("Discord Message Indexer Bot")
    print("Building foundation for AI-powered search")
    print("=" * 50)

    asyncio.run(main())
