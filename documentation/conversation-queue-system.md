# Conversation Queue System Documentation

## Overview

The Discord-Indexer conversation queue system provides stateless, fair, and scalable processing of user conversation requests through Discord Direct Messages (DMs). The system replaced the previous session-based architecture to provide more reliable, independent request processing with anti-spam protection and comprehensive error handling.

## System Architecture

### Core Components

#### 1. ConversationQueue (`src/llm/agents/conversation_queue.py`)
The central queue management system that handles:
- **Thread-safe request queuing** using `asyncio.Queue`
- **Anti-spam protection** preventing multiple concurrent requests per user
- **Request status tracking** through the request lifecycle
- **Queue capacity management** with configurable limits
- **Position tracking** for user queue visibility

#### 2. ConversationQueueWorker (`src/llm/agents/queue_worker.py`)
The worker process that processes queued requests:
- **Async worker loop** for continuous request processing
- **LangChain integration** using `LangChainDMAssistant` for LLM processing
- **Timeout handling** with 60-second request limits
- **Error recovery** with user notifications
- **Stateless processing** without conversation persistence

#### 3. Request Data Structure (`ConversationRequest`)
Each conversation request contains:
- **User identification** (`user_id`, `server_id`)
- **Message content** and processing timestamp
- **Discord integration** (`discord_message_id`, `discord_channel`)
- **Status tracking** (QUEUED � PROCESSING � COMPLETED/FAILED)
- **Optional status message ID** for real-time updates

## Queue Architecture Overview

### Request Flow
```
Discord !ask Command � ConversationQueue � ConversationQueueWorker � LangChain Agent � Discord Response
```

### Queue States
1. **QUEUED** - Request waiting for processing
2. **PROCESSING** - Currently being handled by worker
3. **COMPLETED** - Successfully processed and responded
4. **FAILED** - Processing failed with error handling

### Thread Safety
- All queue operations use `asyncio` primitives
- Request tracking uses `asyncio.Lock` for state consistency
- Worker coordination prevents race conditions
- Statistics and status updates are atomic

## Anti-Spam Protection

### Per-User Request Limiting
The system implements comprehensive anti-spam protection:

#### Single Active Request Rule
- **One request per user**: Users cannot queue multiple requests simultaneously
- **Active request tracking**: System tracks both queued and processing requests
- **Automatic cleanup**: Completed requests free up user slots immediately

#### Implementation Details
```python
def is_user_queued(self, user_id: str) -> bool:
    """Check if user already has a request queued or processing."""
    return user_id in self._active_requests

async def add_request(self, user_id: str, server_id: str, message: str, ...):
    """Add request with anti-spam checking."""
    if self.is_user_queued(user_id):
        logger.warning(f"User {user_id} already has active request, rejecting new request")
        return False
```

#### Queue Capacity Protection
- **Maximum queue size**: Configurable limit (default: 50 requests)
- **Graceful rejection**: Full queue requests are rejected with user notification
- **Fair processing**: First-in-first-out processing order

## Queue Processing Workflow

### Worker Loop Operation
The `ConversationQueueWorker` operates a continuous processing loop:

#### 1. Request Retrieval
```python
async def _worker_loop(self) -> None:
    while self.running:
        request = await self.queue.get_next_request()
        if request is None:
            await asyncio.sleep(1.0)  # Poll for new requests
            continue
```

#### 2. Status Updates
- **Processing notification**: "> **Processing your request...**"
- **Real-time updates**: Edit Discord messages for status changes
- **Error notifications**: Specific error messages for timeouts/failures

#### 3. LLM Processing
```python
response = await asyncio.wait_for(
    self.dm_assistant.respond_to_dm(
        message=request.message,
        user_id=request.user_id,
        user_name=f"User_{request.user_id}",
        server_id=request.server_id
    ),
    timeout=60  # 60-second timeout
)
```

#### 4. Response Delivery
- **Discord channel integration**: Send responses directly to user DMs
- **Error handling**: Timeout and processing error notifications
- **Request completion**: Clean up tracking and update statistics

## Conversation Flow Control

### Stateless Processing Model
The system operates without persistent conversation sessions:

#### Independent Request Processing
- **No conversation history persistence**: Each request processed independently
- **Context through database**: Historical context retrieved per-request from ChromaDB
- **Fair resource usage**: No long-running sessions consuming resources

#### Server Selection Integration
- **Multi-server support**: Users can specify target server in requests
- **Server format**: `!ask [ServerName] question` or `!ask [1] question`
- **Automatic detection**: Single server users bypass selection process

#### Request Format Parsing
```python
# Parse server selection from request
server_pattern = r'^\[(.*?)\]\s*(.*)'
server_match = re.match(server_pattern, message.strip())

if server_match:
    server_selection = server_match.group(1).strip()
    actual_message = server_match.group(2).strip()
```

### Message Routing Logic

#### Discord Command Integration
The `!ask` command in `src/bot/actions.py` integrates with the queue:

1. **Input validation**: Check message content and DM-only requirement
2. **Server resolution**: Parse server selection or present options
3. **Queue submission**: Add validated request to conversation queue
4. **User feedback**: Provide queue position and processing status

#### Queue Position Tracking
```python
def get_queue_position(self, user_id: str) -> Optional[int]:
    """Get user's position in queue (1-based)."""
    if user_id not in self._active_requests:
        return None
    try:
        return self._queue_order.index(user_id) + 1
    except ValueError:
        return None
```

## Session Management and Stateless Operations

### Migration from Session-Based Architecture
The system migrated from persistent sessions to stateless processing:

#### Previous Session Model (Deprecated)
- **Persistent user sessions** with timeout handling
- **Server selection state** maintained across interactions
- **Memory overhead** from long-running session objects
- **Complex cleanup** with timeout notifications

#### Current Stateless Model
- **Independent request processing** without session state
- **Direct server specification** in each request
- **Immediate resource cleanup** after request completion
- **Simplified error handling** without session state corruption

### Session Manager Deprecation
The `SessionManager` class (`src/llm/agents/session_manager.py`) is marked as deprecated:
- **� DEPRECATED**: No longer used in Phase 1 implementation
- **Compatibility preservation**: Kept for potential rollback scenarios
- **Future removal**: Will be removed in subsequent versions

## Integration Points

### Discord Bot Integration

#### Bot Initialization (`src/bot/actions.py`)
```python
# Initialize queue worker with LangChain
from src.ai.agents.queue_worker import initialize_queue_worker
queue_worker = initialize_queue_worker(use_langchain=True)
await queue_worker.start()
bot.queue_worker = queue_worker
```

#### Command Handler Integration
```python
@bot.command(name='ask')
async def ask_command(ctx: commands.Context, *, message: str = None):
    """Ask the DMAssistant a question (stateless queue-based processing)."""
    # Server selection and validation logic
    # Queue request submission
    success = await queue.add_request(
        user_id=str(ctx.author.id),
        server_id=selected_server.server_id,
        message=actual_message,
        discord_channel=ctx.channel
    )
```

### LLM Agent Integration

#### LangChain DMAssistant Connection
The queue worker integrates with `LangChainDMAssistant`:
- **Tool-calling support**: Access to server search and conversation tools
- **Async processing**: Non-blocking LLM request handling
- **Server-specific context**: Each request includes target server information
- **Error propagation**: LLM errors handled and communicated to users

#### Response Generation Flow
1. **Queue retrieval**: Worker gets next request from queue
2. **LLM invocation**: LangChain agent processes user message
3. **Tool execution**: Search tools access ChromaDB for context
4. **Response generation**: LLM generates contextual response
5. **Discord delivery**: Response sent to user's DM channel

## Error Handling & Recovery

### Queue-Level Error Handling

#### Request Validation Errors
- **Empty message content**: User guidance provided
- **Invalid server selection**: Available options presented
- **DM channel requirement**: Command usage instructions

#### Queue Capacity Errors
- **Full queue rejection**: "Queue is full" notification
- **Duplicate request prevention**: Anti-spam messaging
- **Resource exhaustion**: Graceful degradation

### Worker-Level Error Recovery

#### Timeout Handling
```python
except asyncio.TimeoutError:
    logger.error(f"Request timed out for user {request.user_id} after {timeout_seconds} seconds")
    if request.discord_channel:
        await request.discord_channel.send(
            "� **Request Timeout**: Your request took too long to process. "
            "Please try again with a simpler question."
        )
    return False
```

#### Processing Errors
```python
except Exception as e:
    logger.error(f"Error processing request for user {request.user_id}: {e}")
    if request.discord_channel:
        await request.discord_channel.send(
            "L **Processing Error**: Something went wrong while processing your request. "
            "Please try again later."
        )
    return False
```

#### Worker Recovery Mechanisms
- **Exception isolation**: Individual request failures don't stop worker
- **Automatic retry delay**: Brief pause after errors before continuing
- **Graceful shutdown**: Clean worker termination during bot shutdown
- **Resource cleanup**: Proper Discord channel and memory management

### Statistics and Monitoring

#### Queue Performance Metrics
```python
def get_stats(self) -> Dict[str, int]:
    return {
        "queue_size": self.get_queue_size(),
        "active_requests": len(self._active_requests),
        "total_processed": self._total_processed,
        "total_failed": self._total_failed,
        "max_queue_size": self.max_queue_size
    }
```

#### Monitoring Capabilities
- **Real-time queue depth**: Current number of pending requests
- **Processing statistics**: Success/failure rates over time
- **User tracking**: Active requests per user for anti-spam
- **Performance metrics**: Request processing times and throughput

## Configuration Options

### Queue Configuration
```python
class ConversationQueue:
    def __init__(self, max_queue_size: int = 50, request_timeout: int = 300):
        """Initialize conversation queue with configurable limits."""
```

### Worker Configuration
```python
class ConversationQueueWorker:
    def __init__(self, dm_assistant=None, use_langchain: bool = True):
        """Initialize with LangChain or legacy assistant."""
```

### Global Instance Management
Both queue and worker use singleton patterns with explicit initialization:
```python
def initialize_conversation_queue(max_queue_size: int = 50, request_timeout: int = 300):
def initialize_queue_worker(dm_assistant=None, use_langchain: bool = True):
```

## Best Practices and Recommendations

### Performance Optimization
1. **Queue depth monitoring**: Alert on unusual queue growth
2. **Request timeout tuning**: Balance response time vs complexity
3. **Worker scaling**: Consider multiple workers for high load
4. **Memory management**: Regular cleanup of completed requests

### Reliability Improvements
1. **Health check integration**: Monitor worker and queue health
2. **Graceful degradation**: Maintain functionality during partial failures
3. **Request persistence**: Consider database persistence for critical requests
4. **Load balancing**: Distribute requests across multiple workers

### User Experience Enhancements
1. **Progress indicators**: Real-time processing status updates
2. **Queue position feedback**: Show user position in processing queue
3. **Estimated wait times**: Provide processing time estimates
4. **Request history**: Allow users to view recent request status

### Security Considerations
1. **Rate limiting**: Additional protection beyond per-user limits
2. **Input validation**: Comprehensive message content sanitization
3. **Resource limits**: Memory and CPU usage monitoring
4. **Error information**: Limit error details exposed to users

## Future Development Considerations

### Scalability Enhancements
- **Distributed queue system**: Redis-based queue for multi-instance deployments
- **Worker pool management**: Dynamic worker scaling based on load
- **Request prioritization**: Premium users or request type priority
- **Load balancing**: Geographic or capability-based request routing

### Feature Extensions
- **Conversation context**: Optional conversation history preservation
- **Multi-turn conversations**: Support for follow-up questions
- **Request scheduling**: Delayed or recurring request processing
- **Analytics integration**: Detailed usage and performance analytics

### Integration Improvements
- **Webhook support**: External system notifications for queue events
- **API endpoints**: RESTful interface for queue management
- **Monitoring dashboards**: Real-time visualization of queue metrics
- **Administrative tools**: Queue management and user administration interfaces