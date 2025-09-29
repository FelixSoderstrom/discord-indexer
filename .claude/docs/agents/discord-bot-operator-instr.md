# Discord Bot Operator Agent Instructions

## Key Areas of Focus
- `src/bot/client.py` - Main Discord bot client implementation with pipeline coordination
- `src/bot/actions.py` - Bot event handlers, commands, and startup/shutdown sequences
- `src/bot/rate_limiter.py` - Discord API rate limiting with smart resumption capabilities
- `main.py` - Bot initialization, model health checks, and system startup orchestration

## Specific Responsibilities

### Discord.py Bot Management
- **Bot Lifecycle**: Complete startup sequence with server configuration, pipeline initialization, and LangChain DMAssistant setup
- **Connection Management**: Discord connection handling with proper intents (message_content, guilds, guild_messages, members)
- **Graceful Shutdown**: Comprehensive cleanup sequence clearing queue workers, pipeline references, and Discord connections
- **Event Coordination**: Event-based message routing between DMs, server messages, and commands using Discord.py commands extension

### Real-time Message Processing Coordination
- **Pipeline Integration**: Coordinate with MessagePipeline using `completion_event` for backpressure management
- **Message Data Extraction**: Rich metadata extraction from Discord messages with comprehensive author, channel, and guild information
- **Batch Processing**: Send single messages or batches to pipeline using `send_batch_to_pipeline()` with async coordination
- **Smart Resumption**: Server-by-server checkpoint-based processing using `resume_indexing_from_checkpoints()`

### Discord API Integration & Rate Limiting
- **Rate Compliance**: Implement Discord's 50 requests/second limit with burst handling and semaphore-based control
- **Parallel Processing**: Separate rate-limited fetching from unlimited parallel processing of fetched data
- **Smart Fetching**: Support both full historical fetching and timestamp-based resumption fetching
- **Automatic Retry**: HTTP 429 handling with exponential backoff and configurable retry limits
- **Concurrent Channel Processing**: Batch channel processing with configurable concurrency limits

### Queue-based Conversation System
- **LangChain Integration**: Initialize and coordinate with LangChainDMAssistant for conversation handling
- **Queue Worker Management**: Start/stop ConversationQueueWorker with proper cleanup during shutdown
- **Stateless Processing**: Support fair queue-based conversation processing without persistent sessions
- **Command Handling**: DM-only command enforcement with server selection logic for multi-server users

## Current Architecture Patterns

### Bot Client Structure
```python
class DiscordBot(commands.Bot):
    def __init__(self):
        # Pipeline coordination
        self.pipeline_ready = asyncio.Event()
        self.message_pipeline: Optional["MessagePipeline"] = None
        self.batch_size = 1000

        # DMAssistant coordination
        self.dm_assistant: Optional["DMAssistant"] = None
        self.queue_worker = None

        # Rate limiting and processing state
        self.rate_limiter = DiscordRateLimiter()
        self.stored_messages: List[Dict[str, Any]] = []  # Legacy
        self.processed_channels: List[int] = []
```

### Event Handling Flow
- **on_ready_handler**: Server configuration → Pipeline init → DMAssistant setup → Queue worker start → Historical processing → Real-time monitoring
- **on_message_handler**: Bot message filtering → DM routing → Server message processing → Command delegation
- **Message Routing**: DM guidance vs server indexing vs command processing

### Coordination Boundaries
- **Coordinates WITH MessagePipeline**: Provides structured message data and waits for completion events
- **Coordinates WITH ConversationQueueWorker**: Manages lifecycle but doesn't implement queue processing logic
- **Coordinates WITH Rate Limiter**: Uses for all Discord API calls but doesn't implement rate limiting logic
- **Does NOT**: Implement message processing, embedding, extraction, or storage logic
- **Does NOT**: Implement conversation AI logic or queue management algorithms
- **Does NOT**: Handle database operations beyond coordination

## Implementation Patterns

### Smart Resumption System
- Server-by-server processing with individual checkpoint tracking
- Support for full historical processing vs resumption from last timestamp
- Batch processing (5 channels at a time, 1000 messages per channel)
- Integration with `get_server_indexing_status()` for resumption decisions

### Rate Limiting Strategy
- Semaphore-based concurrency control
- Request timing tracking with deque-based sliding window
- Automatic retry with configurable delays
- Support for burst handling up to configured limits

### Message Data Structure
- Comprehensive metadata extraction including author details, channel info, guild data
- Attachment URL preservation and embed detection
- Timestamp handling with ISO format
- Reply reference tracking

## Testing Approach
- **Integration Testing**: Test complete startup sequence including model health checks
- **Message Processing**: Validate message routing, extraction, and pipeline coordination
- **Rate Limiting**: Test batch fetching under various load conditions
- **Error Handling**: Validate graceful degradation and shutdown sequences
- **Command Testing**: Test DM-only commands and server selection logic

## Error Handling Standards
- **Specific Exception Handling**: Use Discord-specific exceptions (HTTPException, Forbidden, NotFound)
- **Startup Failures**: Critical component failures trigger immediate shutdown with sys.exit(1)
- **Runtime Resilience**: Message processing errors don't crash the bot
- **Graceful Degradation**: Continue operation with reduced functionality when possible
- **Comprehensive Logging**: Error tracking without exposing sensitive data

## Performance Considerations
- **Backpressure Management**: Pipeline coordination prevents memory overflow
- **Concurrent Processing**: Configurable channel concurrency (default 5 concurrent channels)
- **Memory Efficiency**: Batch processing with controlled sizes
- **Model Preloading**: BGE embedding model preloading to prevent runtime delays
- **Checkpoint Optimization**: Smart resumption reduces redundant processing