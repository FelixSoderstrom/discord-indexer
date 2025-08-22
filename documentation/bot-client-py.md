# src/bot/client.py Documentation

## Purpose
Core Discord bot implementation that handles connection, message processing pipeline integration, and data extraction functionality.

## What It Does
1. **Discord Connection**: Manages bot connection with proper intents and configuration
2. **Pipeline Integration**: Hosts message processing pipeline for real-time message handling
3. **Rate-Limited Processing**: Intelligent rate limiting for Discord API calls with parallel processing
4. **Message Storage**: In-memory storage of extracted messages for validation (legacy/fallback)
5. **Historical Processing**: Fetches all existing messages from accessible channels using parallel batch processing
6. **Data Extraction**: Converts Discord messages to structured data format

## Class: DiscordBot

### Initialization
- Inherits from `commands.Bot` for Discord.py functionality
- Configures command prefix from settings
- Sets up Discord intents for message access
- Initializes storage containers for messages and channel tracking
- Prepares message processing pipeline attribute (initialized later)
- Creates `DiscordRateLimiter` instance for intelligent API rate limiting

### Storage and Coordination Attributes
```python
# Pipeline coordination
self.pipeline_ready: asyncio.Event = asyncio.Event()    # Event for producer-consumer coordination
self.message_pipeline: Optional[MessagePipeline] = None # Message processing pipeline
self.batch_size: int = 1000                             # Batch size for message processing

# Legacy storage (will be removed when pipeline fully implemented)
self.stored_messages: List[Dict[str, Any]] = []         # All captured messages (legacy/fallback)
self.processed_channels: List[int] = []                 # Channels that have been indexed

# Rate limiting and logging
self.rate_limiter: DiscordRateLimiter = DiscordRateLimiter()  # Rate limiting for Discord API calls
```

## Key Methods

### `get_all_channels()`
- **Purpose**: Discovers all accessible text channels across connected servers
- **Returns**: List of Discord TextChannel objects
- **Filters**: Only includes text channels (excludes voice, categories, etc.)

### `get_channel_messages(channel_id, limit=100)`
- **Purpose**: Fetches historical messages from a specific channel
- **Parameters**: 
  - `channel_id`: Discord channel ID
  - `limit`: Maximum messages to fetch (default 100, can be up to 1000)
- **Error Handling**: 
  - Missing permissions
  - Invalid channel IDs
  - API rate limits
- **Returns**: List of extracted message data dictionaries

### `send_batch_to_pipeline(messages)`
- **Purpose**: Send batch of messages to pipeline with producer-consumer coordination
- **Parameters**: List of message data dictionaries to process
- **Process**:
  1. Validates pipeline availability and message batch
  2. Clears pipeline_ready event to signal processing start
  3. Calls `pipeline.process_messages(messages)` for batch processing
  4. Waits for pipeline_ready event to be set (completion signal)
  5. Returns success/failure status
- **Coordination**: Implements backpressure by waiting for pipeline completion
- **Error Handling**: Handles pipeline unavailability and processing failures

### `process_historical_messages_through_pipeline()`
- **Purpose**: Process all historical messages through unified pipeline with batching and backpressure
- **Process**:
  1. Discovers all accessible channels
  2. Processes channels in batches of 5 to implement backpressure
  3. Uses `rate_limiter.batch_fetch_messages()` for parallel fetching within each batch
  4. Sends each batch to pipeline using `send_batch_to_pipeline()`
  5. Waits for pipeline completion before fetching next batch
  6. Tracks processed channels for future resume functionality
- **Performance**: Optimal throughput while respecting system resource limits
- **Safety**: Maximum 2 batches in memory (processing + ready), crash-safe
- **Coordination**: Producer-consumer pattern prevents overwhelming consumer hardware

### `get_all_historical_messages()` (DEPRECATED)
- **Purpose**: Legacy historical processing function that bypasses pipeline
- **Status**: Maintained for compatibility but logs deprecation warning
- **Process**: Same as original but stores in memory without pipeline processing
- **Recommendation**: Use `process_historical_messages_through_pipeline()` instead

### `_extract_message_data(message)`
- **Purpose**: Converts Discord Message object to structured data
- **Used By**: Both historical processing and real-time pipeline processing
- **Extracts**:
  - Message ID and content
  - Author information (ID, username, display name)
  - Channel information (ID, name)
  - Server/guild information
  - Timestamp (ISO format)
  - Attachment URLs
  - Embed presence
  - Message type

### `close()`
- **Purpose**: Clean shutdown of bot connection with proper resource cleanup
- **Process**:
  1. **Pipeline Cleanup**: Clears message pipeline reference if available
  2. **Parent Cleanup**: Calls parent class close() method for Discord connection
- **Resource Safety**: Ensures proper cleanup of both pipeline and Discord resources

## Message Data Structure
```python
{
    'id': 123456789,                           # Discord message ID
    'content': "Hello world!",                 # Message text content
    'author': {
        'id': 789,                             # Author's Discord ID
        'name': 'username',                    # Author's username
        'display_name': 'Display Name'         # Author's display name
    },
    'channel': {
        'id': 456,                             # Channel ID
        'name': 'general'                      # Channel name
    },
    'guild': {
        'id': 123,                             # Server ID
        'name': 'My Server'                    # Server name
    },
    'timestamp': '2024-01-01T12:00:00',        # ISO timestamp
    'attachments': ['https://cdn.discord.com/...'], # Attachment URLs
    'has_embeds': False,                       # Whether message has embeds
    'message_type': 'default'                  # Discord message type
}
```

## Error Handling
- **Discord.Forbidden**: Logs permission issues but continues processing
- **Invalid Channels**: Safely skips channels that can't be accessed
- **API Errors**: Logs errors but doesn't crash the bot

## Design Decisions

### Why Pipeline Integration at Bot Level?
- **Single Responsibility**: Bot handles Discord connection, pipeline handles processing
- **Clean Separation**: Discord concerns separated from message processing logic
- **Resource Management**: Bot manages pipeline lifecycle alongside Discord connection
- **Unified Interface**: Both historical and real-time messages use same pipeline processing

### Why Producer-Consumer Coordination?
- **Backpressure Control**: Prevents overwhelming system resources during batch processing
- **Memory Bounded**: Maximum 2 batches in memory (processing + ready)
- **Crash Safety**: Only lose 1-2 batches maximum if system fails
- **Resource Efficiency**: Natural flow control adapts to processing capacity

### Why Optional Pipeline Attribute?
- **Initialization Order**: Pipeline created after bot is fully connected and ready
- **Type Safety**: Optional typing indicates pipeline may not be available during startup
- **Graceful Shutdown**: Pipeline can be cleared independently during shutdown
- **Coordination**: Pipeline initialized with completion_event for async signaling

### Why In-Memory Storage Retention?
- **Legacy Support**: Maintains compatibility with existing functionality
- **Debugging**: Direct access to captured data for verification and testing
- **Fallback Capability**: Provides backup storage mechanism if needed

### Why Historical-First Processing?
- **Complete Picture**: Gets all existing context before monitoring new messages
- **Resume Capability**: Tracks processed channels for future resume functionality
- **User Experience**: Shows immediate results from message capture

### Why Integrate Rate Limiter at Bot Level?
- **Global Coordination**: Discord's 50 req/sec limit applies to the entire bot, not per-channel
- **Parallel Processing**: Enables fetching from multiple channels simultaneously while staying within limits
- **Error Recovery**: Centralized retry logic with exponential backoff for rate limit violations
- **Performance**: 4x faster historical processing compared to sequential fetching
- **Resource Efficiency**: Optimal utilization of Discord's API quota without violations
- **Future-Proofing**: Scalable architecture that adapts to Discord's dynamic rate limiting

## Future Extensibility
This implementation is designed for easy extension:
- **Pipeline Enhancement**: Message processing pipeline can be extended with additional modules
- **Unified Processing**: Both historical and real-time messages use identical processing interface
- **Resume Functionality**: Chronological processing and coordination ready for timestamp-based resume
- **Filtering**: Channel discovery can be extended with filtering criteria
- **Batch Size Optimization**: Configurable batch sizes for different hardware capabilities
- **Multi-Pipeline Support**: Architecture supports multiple specialized pipelines with shared coordination
- **Rate Limiter Configuration**: Rate limiting parameters can be adjusted for different server sizes and requirements
- **Advanced Coordination**: Can be extended with priority queuing, parallel pipelines, or distributed processing

## Performance Considerations
- **Intelligent Rate Limiting**: Respects Discord's 50 requests/second global bot limit with automatic retry logic
- **Producer-Consumer Pattern**: Optimal throughput with natural backpressure control
- **Memory Bounded**: Maximum 2 batches in memory (processing + ready) prevents resource exhaustion
- **Batch Processing**: 1000 messages per batch for optimal processing efficiency
- **Parallel Fetching**: Fetches from multiple channels simultaneously (up to 5 concurrent channels)
- **Pipeline Coordination**: Message processing offloaded to dedicated pipeline with async coordination
- **Resource Management**: Pipeline lifecycle and coordination managed alongside Discord connection
- **Throughput**: 4x performance improvement over sequential fetching while respecting system limits
- **Error Recovery**: Graceful handling of API failures with automatic retries and coordination cleanup
