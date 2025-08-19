import asyncio
import logging
from src.config.settings import settings
from src.bot.client import DiscordBot
from src.bot.actions import setup_bot_actions


async def main():
    """Main execution flow - orchestrates the Discord bot."""
    print("🚀 Starting Discord Indexer Bot...")
    
    # Setup logging based on DEBUG setting
    log_level = logging.INFO if settings.DEBUG else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create bot instance
    print("🤖 Creating bot instance...")
    bot = DiscordBot()
    
    # Setup actions and event handlers
    print("⚙️  Setting up event handlers...")
    setup_bot_actions(bot)
    
    # Start bot with token
    print("🔐 Connecting to Discord...")
    try:
        await bot.start(settings.DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        await bot.close()
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")
        logging.error(f"Bot startup error: {e}")
        await bot.close()


if __name__ == "__main__":
    print("=" * 50)
    print("Discord Message Indexer Bot")
    print("Building foundation for AI-powered search")
    print("=" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Critical error: {e}")
        logging.critical(f"Critical startup error: {e}")