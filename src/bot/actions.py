import discord
from discord.ext import commands


async def on_ready_handler(bot: commands.Bot):
    """Handle bot ready event - start monitoring for new messages."""
    print("=== Bot is ready! Now monitoring for new messages... ===")
    
    # Log available channels for info
    channels = bot.get_all_channels()
    print(f"📡 Monitoring {len(channels)} channels for new messages")


async def on_message_handler(bot: commands.Bot, message: discord.Message):
    """Handle new incoming messages."""
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Extract and store the new message
    message_data = bot._extract_message_data(message)
    bot.stored_messages.append(message_data)
    
    print(f"📨 New message: #{message.channel.name} - {message.author.name}: {message.content[:30]}...")


def setup_bot_actions(bot: commands.Bot):
    """Setup event handlers for the bot."""
    
    @bot.event
    async def on_ready():
        """Event when bot connects to Discord."""
        await on_ready_handler(bot)
    
    @bot.event
    async def on_message(message):
        """Event when new message is received."""
        await on_message_handler(bot, message)
    
    print("✅ Bot event handlers registered")
