# src/bot/actions.py Documentation

## Purpose
Event handler system for Discord bot events with message processing pipeline integration. Manages bot's response to Discord events and coordinates message processing through the pipeline architecture.

## What It Does
1. **Event Registration**: Registers Discord event handlers with the bot instance
2. **Pipeline Initialization**: Sets up message processing pipeline when bot connects
3. **Real-time Processing**: Processes new messages through complete pipeline workflow
4. **Fail-Fast Error Handling**: Shuts down application on pipeline failures

## Event Handlers

### `on_ready_handler(bot)`
**Triggered**: When bot successfully connects to Discord

**Process**:
1. **Pipeline Initialization**: Creates and initializes `MessagePipeline` instance
2. **Pipeline Assignment**: Assigns pipeline to bot instance (`bot.message_pipeline`)
3. **Channel Discovery**: Logs available channels for monitoring
4. **Status Confirmation**: Reports successful initialization

**Console Output Example**:
```
=== Bot is ready! Now monitoring for new messages... ===
🔧 Initializing message processing pipeline...
✅ Message pipeline initialized successfully
📡 Monitoring 5 channels for new messages
```

### `on_message_handler(bot, message)`
**Triggered**: When any new message is sent in accessible channels

**Filtering Logic**:
1. **Skip Bot Messages**: Ignores messages from the bot itself
2. **Pipeline Availability Check**: Verifies pipeline is initialized and available
3. **Critical Failure Handling**: Shuts down application if pipeline unavailable

**Process**:
1. **Message Extraction**: Uses `bot._extract_message_data(message)`
2. **Pipeline Processing**: Calls `bot.message_pipeline.process_message(message_data)`
3. **Success Verification**: Checks pipeline processing success
4. **Fail-Fast Behavior**: Shuts down application on processing failures

**Console Output Example**:
```
📨 Processing new message: #general - username: Hey, just wanted to share this...
```

**Critical Error Example**:
```
❌ Message pipeline not available - application is fundamentally broken
🛑 Shutting down application - cannot process messages without pipeline
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

### Why Pipeline Initialization in on_ready?
- **Single Initialization**: Ensures pipeline is ready before any message processing
- **Clear Lifecycle**: Pipeline created when bot is fully connected and ready
- **Fail-Fast Setup**: Immediate indication if pipeline initialization fails

### Why Fail-Fast Error Handling?
- **Application Integrity**: Prevents running in degraded state with broken core functionality
- **Clear Feedback**: Immediate indication when core processing fails
- **Operational Safety**: Avoids accumulating unprocessed messages or inconsistent state

## Message Flow

### Startup Flow
```
Bot Connects → on_ready_handler() → Pipeline Initialization → Real-time Monitoring
```

### Real-time Flow
```
New Message → on_message_handler() → Pipeline Processing → Database Storage → Ready for Next
```

### Failure Flow
```
Pipeline Failure → Critical Error Logging → Application Shutdown (sys.exit(1))
```

## Error Handling
- **Critical Failure Detection**: Pipeline unavailability or processing failures trigger shutdown
- **No Fallback Mechanisms**: Application does not operate in degraded modes
- **Clean Shutdown**: Proper logging and graceful application termination

## Future Extensibility
This event system is designed for easy extension:
- **Additional Events**: Easy to add handlers for message edits, deletions, reactions
- **Pipeline Extensions**: Message processing pipeline can be extended with additional processing modules
- **Processing Hooks**: Pre and post-processing hooks can be added to pipeline workflow
- **Monitoring Integration**: Event handlers can trigger monitoring and alerting systems

## Console Output Purpose
The console output serves multiple purposes:
- **Development Validation**: Confirms bot is processing messages correctly through pipeline
- **Debugging**: Shows real-time pipeline activity and processing status
- **Error Diagnosis**: Clear indication of pipeline failures and shutdown reasons
- **Operational Monitoring**: Processing statistics and pipeline health status
