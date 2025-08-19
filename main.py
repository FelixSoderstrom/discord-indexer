import asyncio
import logging
from typing import NoReturn
from src.config.settings import settings
from src.bot.client import DiscordBot
from src.bot.actions import setup_bot_actions


async def main() -> None:
    """Main execution flow - orchestrates the Discord bot.
    
    Sets up logging, creates bot instance, configures event handlers,
    and starts the Discord connection with proper error handling.
    """
    logger = logging.getLogger(__name__)
    
    # Setup logging based on DEBUG setting
    log_level = logging.INFO if settings.DEBUG else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Starting Discord Indexer Bot...")
    
    try:
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
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    print("=" * 50)
    print("Discord Message Indexer Bot")
    print("Building foundation for AI-powered search")
    print("=" * 50)

    asyncio.run(main())