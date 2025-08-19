# src/bot/actions.py Documentation

## Purpose
Event handler system for Discord bot events. Manages the bot's response to Discord events like connection and new messages.

## What It Does
1. **Event Registration**: Registers Discord event handlers with the bot instance
2. **Historical Processing**: Handles initial message indexing when bot starts
3. **Real-time Monitoring**: Captures new messages as they arrive
4. **Validation Output**: Provides console feedback for message capture

## Event Handlers

### `on_ready_handler(bot)`
**Triggered**: When bot successfully connects to Discord

**Process**:
1. **Historical Message Processing**: Calls `bot.get_all_historical_messages()`
2. **Progress Reporting**: Shows total messages captured
3. **Sample Display**: Prints first 3 messages for validation
4. **Status Update**: Confirms transition to real-time monitoring

**Console Output Example**:
```
=== Bot is ready! Starting historical message processing ===
✅ Historical processing complete: 47 messages stored

=== Sample Messages ===
[2024-01-15T10:30:00] #general - username: Hello everyone, how's it going...
[2024-01-15T11:15:00] #random - otheruser: Check out this cool link...
[2024-01-15T12:00:00] #general - username: Anyone available for a quick call...
=== End Sample ===

🔄 Now monitoring for new messages...
```

### `on_message_handler(bot, message)`
**Triggered**: When any new message is sent in accessible channels

**Filtering Logic**:
1. **Skip Bot Messages**: Ignores messages from the bot itself
2. **Historical Processing Check**: Skips messages from channels still being processed
3. **Channel Verification**: Only processes messages from already-indexed channels

**Process**:
1. **Message Extraction**: Uses `bot._extract_message_data(message)`
2. **Storage**: Appends to `bot.stored_messages` list
3. **Notification**: Prints real-time message notification

**Console Output Example**:
```
📨 New message: #general - username: Hey, just wanted to share this...
```

## Setup Function

### `setup_bot_actions(bot)`
**Purpose**: Registers event handlers with the Discord bot instance

**Registration Process**:
```python
@bot.event
async def on_ready():
    """Event when bot connects to Discord."""
    await on_ready_handler(bot)

@bot.event
async def on_message(message):
    """Event when new message is received."""
    await on_message_handler(bot, message)
```

**Confirmation**: Prints "✅ Bot event handlers registered" when complete

## Design Decisions

### Why Separate Handler Functions?
- **Testability**: Handler logic can be tested independently
- **Reusability**: Handlers can be called from different contexts
- **Maintainability**: Clean separation between event registration and logic

### Why Historical Processing in on_ready?
- **Complete Context**: Ensures all existing messages are captured before monitoring new ones
- **Single Processing Pass**: Avoids duplicate processing of historical messages
- **User Feedback**: Immediate validation that the bot is working

### Why Channel Tracking?
- **Prevents Duplicates**: Ensures real-time handler doesn't process messages during historical indexing
- **Resume Capability**: Foundation for future resume-from-timestamp functionality
- **Processing State**: Clear distinction between initialization and monitoring phases

## Message Flow

### Startup Flow
```
Bot Connects → on_ready_handler() → Historical Processing → Real-time Monitoring
```

### Real-time Flow
```
New Message → on_message_handler() → Filter Checks → Extract & Store → Notification
```

## Error Handling
- **Exception Catching**: Historical processing errors are caught and logged
- **Graceful Degradation**: Errors don't prevent transition to real-time monitoring
- **Filtering Safety**: Multiple checks prevent processing unwanted messages

## Future Extensibility
This event system is designed for easy extension:
- **Additional Events**: Easy to add handlers for message edits, deletions, reactions
- **Processing Pipeline**: Message extraction can be extended with additional processing steps
- **Database Integration**: Storage calls can be replaced with database operations
- **Webhooks**: Event handlers can trigger external APIs or webhooks

## Console Output Purpose
The console output serves multiple purposes:
- **Development Validation**: Confirms bot is capturing messages correctly
- **Debugging**: Shows real-time activity for troubleshooting
- **Progress Tracking**: Historical processing progress and completion
- **Sample Data**: Immediate validation of data structure and content
