# Queue System Architecture Documentation

## Overview
Thread-safe conversation queuing system for managing DMAssistant requests with anti-spam protection, database integration, and asynchronous processing.

## Core Components

### ConversationQueue Class
**Purpose**: Thread-safe queue for managing conversation requests

**Key Features**:
- Anti-spam protection (one request per user)
- Queue size limits with overflow protection
- Conversation history loading from database
- Message persistence after processing
- Real-time statistics and monitoring

### ConversationQueueWorker Class
**Purpose**: Asynchronous worker that processes queued requests

**Key Features**:
- Continuous processing loop
- DMAssistant integration
- Database persistence
- Error handling and recovery
- Graceful start/stop

### ConversationRequest Dataclass
**Purpose**: Structured request object for queue items

**Fields**:
- `user_id`: Discord user ID
- `server_id`: Discord server ID  
- `message`: User's message content
- `timestamp`: Request creation time
- `discord_message_id`: Optional Discord message for status updates
- `status`: Current request status (QUEUED, PROCESSING, COMPLETED, FAILED)

## Request Flow

### 1. Request Addition
```
User → Discord → Bot Commands → ConversationQueue.add_request()
```

**Anti-Spam Check**: Reject if user already has active request  
**Queue Capacity**: Reject if queue is full  
**Success**: Add to queue and active tracking

### 2. Request Processing
```
Queue → Worker Loop → DMAssistant → Database Storage → Completion
```

**Worker Loop**: Continuously polls queue for requests  
**History Loading**: Load conversation context from database  
**DMAssistant**: Generate response using loaded context  
**Persistence**: Store both user message and assistant response

### 3. Request Completion
```
Worker → Queue.complete_request() → Remove from active tracking
```

## Database Integration

### Conversation Loading
- Loads up to 20 recent messages per request
- Formats messages for DMAssistant context
- Server-scoped conversation history

### Message Storage
- Stores user message and assistant response
- Maintains conversation continuity
- Thread-safe database operations

## Anti-Spam Protection

### User Request Tracking
- Maps `user_id` to active `ConversationRequest`
- Prevents multiple simultaneous requests per user
- Automatic cleanup on request completion

### Queue Limits
- Maximum queue size protection (default: 50)
- Graceful rejection when queue is full
- Statistics tracking for monitoring

## Error Handling

### Worker Loop Resilience
- Catches and logs processing errors
- Continues operation after individual request failures
- Graceful shutdown on cancellation

### Database Error Handling
- Returns empty history on database errors
- Continues processing even if storage fails
- Comprehensive error logging

## Statistics and Monitoring

### Queue Statistics
- Current queue size
- Active request count
- Total processed requests
- Total failed requests
- Maximum queue capacity

### Performance Monitoring
- Request processing times
- Queue throughput
- Database operation success rates

## Configuration

### Queue Settings
- `max_queue_size`: Maximum requests in queue (default: 50)
- `request_timeout`: Individual request timeout (default: 300s)
- `history_limit`: Messages loaded per request (default: 20)

### Worker Settings
- Polling interval: 1 second when queue is empty
- Error recovery delay: 5 seconds after exceptions
- Graceful shutdown timeout: Immediate cancellation

## Future Enhancements (Phase 6+)

### Message Status Updates
- Real-time queue position updates
- Processing status messages
- Completion notifications

### Advanced Queue Management
- Priority queuing for premium users
- Request scheduling and delays
- Queue persistence across restarts

### Performance Optimizations
- Batch database operations
- Connection pooling
- Memory usage optimization