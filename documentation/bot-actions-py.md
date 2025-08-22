# src/bot/actions.py Documentation

## Purpose
Event handler system for Discord bot events with unified message processing pipeline integration. Manages bot's response to Discord events and coordinates both historical and real-time message processing through producer-consumer pattern.

## What It Does
1. **Event Registration**: Registers Discord event handlers with the bot instance
2. **Pipeline Coordination**: Sets up message processing pipeline with async coordination
3. **Historical Processing**: Processes all historical messages through unified pipeline on startup
4. **Real-time Processing**: Processes new messages through unified pipeline interface
5. **Producer-Consumer Management**: Implements backpressure control for optimal resource usage
6. **Fail-Fast Error Handling**: Shuts down application on pipeline failures

## Event Handlers

### `on_ready_handler(bot)`
**Triggered**: When bot successfully connects to Discord

**Process**:
1. **Pipeline Initialization**: Creates `MessagePipeline` with `completion_event` for coordination
2. **Historical Processing**: Calls `process_historical_messages_through_pipeline()` for complete processing
3. **Success Transition**: Transitions to real-time monitoring after historical completion
4. **Failure Handling**: Shuts down application if historical processing fails

**Console Output Example**:
```
=== Bot is ready! Starting message processing... ===
🔧 Initializing message processing pipeline...
✅ Message pipeline initialized successfully
📜 Starting historical message processing through pipeline...
✅ Historical message processing completed successfully
📡 Now monitoring for new real-time messages...
📡 Monitoring 5 channels for new messages
```

**Producer-Consumer Coordination**:
- Pipeline initialized with `bot.pipeline_ready` event for async coordination
- Historical processing uses batching with backpressure control
- All messages processed through unified interface before real-time monitoring

### `on_message_handler(bot, message)`
**Triggered**: When any new message is sent in accessible channels

**Filtering Logic**:
1. **Skip Bot Messages**: Ignores messages from the bot itself
2. **Pipeline Availability Check**: Verifies pipeline is initialized and available
3. **Critical Failure Handling**: Shuts down application if pipeline unavailable

**Process**:
1. **Message Extraction**: Uses `bot._extract_message_data(message)`
2. **Unified Interface**: Wraps single message in list: `[message_data]`
3. **Pipeline Processing**: Calls `bot.send_batch_to_pipeline([message_data])`
4. **Coordination**: Waits for pipeline completion via producer-consumer pattern
5. **Success Verification**: Checks pipeline processing success
6. **Fail-Fast Behavior**: Shuts down application on processing failures

**Unified Processing**:
- Uses same batch interface as historical processing
- Single message wrapped in list for consistent pipeline interface
- Producer-consumer coordination ensures proper resource management

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
Bot Connects → on_ready_handler() → Pipeline Initialization → Historical Processing → Real-time Monitoring
```

### Historical Processing Flow
```
Historical Batches → send_batch_to_pipeline() → Chronological Sorting → Sequential Processing → Coordination
```

### Real-time Flow
```
New Message → on_message_handler() → Wrap in List → send_batch_to_pipeline() → Pipeline Processing → Coordination
```

### Unified Processing
```
All Messages → send_batch_to_pipeline() → process_messages() → Chronological Order → Sequential Processing
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
- **Resume Functionality**: Historical processing foundation ready for timestamp-based resume
- **Processing Hooks**: Pre and post-processing hooks can be added to pipeline workflow
- **Coordination Extensions**: Producer-consumer pattern can support multiple pipelines
- **Monitoring Integration**: Event handlers can trigger monitoring and alerting systems

## Console Output Purpose
The console output serves multiple purposes:
- **Development Validation**: Confirms bot is processing messages correctly through pipeline
- **Debugging**: Shows real-time pipeline activity and processing status
- **Error Diagnosis**: Clear indication of pipeline failures and shutdown reasons
- **Operational Monitoring**: Processing statistics and pipeline health status
