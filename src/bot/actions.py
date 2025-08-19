import discord
from discord.ext import commands


async def on_ready_handler(bot: commands.Bot):
    """Handle bot ready event - process historical messages first."""
    print("=== Bot is ready! Starting historical message processing ===")
    
    # Process all historical messages
    try:
        historical_messages = await bot.get_all_historical_messages()
        print(f"✅ Historical processing complete: {len(historical_messages)} messages stored")
        
        # Display sample data for validation
        if historical_messages:
            print("\n=== Sample Messages ===")
            for msg in historical_messages[:3]:  # Show first 3 messages
                print(f"[{msg['timestamp']}] #{msg['channel']['name']} - {msg['author']['name']}: {msg['content'][:50]}...")
            print("=== End Sample ===\n")
        
        print("🔄 Now monitoring for new messages...")
        
    except Exception as e:
        print(f"❌ Error during historical processing: {e}")


async def on_message_handler(bot: commands.Bot, message: discord.Message):
    """Handle new incoming messages."""
    # Skip messages from the bot itself
    if message.author == bot.user:
        return
    
    # Skip if still processing historical messages for this channel
    if hasattr(bot, 'processed_channels') and message.channel.id not in bot.processed_channels:
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
