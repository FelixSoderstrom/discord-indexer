# src/db/conversation_db.py Documentation

## Overview
SQLite database management for DMAssistant conversation persistence. Provides server-isolated conversation storage with thread-safe operations and proper user tracking for the multi-user DMAssistant system.

## Database Schema

### conversations Table
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT
);
```

### Indexes
- **idx_user_server**: `(user_id, server_id)` - Fast conversation retrieval
- **idx_timestamp**: `(timestamp)` - Chronological ordering and cleanup
- **idx_session**: `(session_id)` - Session-based queries

## Design Decisions

### Server Isolation
**Requirement**: Users can share servers with the bot, conversations must not leak between servers.

**Implementation**: Every operation requires both `user_id` and `server_id` parameters. Database queries always filter by both fields to ensure complete isolation.

**Benefits**:
- Privacy: Users in Server A cannot see conversations from Server B
- Data integrity: No cross-contamination of conversation contexts
- Scalability: Clean separation for multi-server deployments

### Thread Safety
**Requirement**: Bot handles multiple concurrent Discord events and DMAssistant requests.

**Implementation**: 
- Thread-local locking with `threading.Lock()`
- Context manager pattern for connection cleanup
- `check_same_thread=False` with proper synchronization

**Benefits**:
- Prevents database corruption from concurrent access
- Ensures data consistency across multiple users
- Handles queue-based request processing safely

### Role Constraint
**Requirement**: Conversation messages must be either from user or assistant.

**Implementation**: `CHECK (role IN ('user', 'assistant'))` constraint

**Benefits**:
- Data integrity: Prevents invalid role values
- Clear conversation structure for LLM context loading
- Simplified query logic and validation

### Session Tracking (Optional)
**Field**: `session_id TEXT` (nullable)

**Purpose**: 
- Group related conversation turns
- Future session management features
- Conversation analytics and debugging

**Usage**: Currently optional, can be used for enhanced session management in later phases.

## Class Architecture

### ConversationDatabase Class
**Thread-safe SQLite manager with lazy initialization**

#### Core Methods
- `add_message()`: Store conversation messages with validation
- `get_conversation_history()`: Retrieve chronological message history
- `clear_user_conversation_history()`: Delete user's server-specific history
- `get_conversation_count()`: Count messages for user+server combination

#### Utility Methods
- `get_active_users()`: Find recently active users in server
- `get_database_stats()`: Database metrics for monitoring
- `cleanup_old_conversations()`: Remove old messages for maintenance

#### Error Handling
- **Specific exceptions**: Catches `sqlite3.IntegrityError` separately from `sqlite3.Error`
- **Graceful degradation**: Returns empty lists/False on errors rather than crashing
- **Logging**: Comprehensive error logging with context information

### Global Instance Management
```python
def get_conversation_db() -> ConversationDatabase:
    """Lazy-loaded global instance"""

def initialize_conversation_db() -> None:
    """Explicit initialization for startup"""
```

**Pattern**: Singleton pattern with explicit initialization option for startup control.

## Integration Points

### Startup Integration
**File**: `src/db/setup_db.py` - `initialize_db()`
- Conversation database initialized alongside ChromaDB
- Database directory creation with proper error handling
- Logging coordination with existing database setup

### DMAssistant Integration
**Usage Pattern**:
```python
from db.conversation_db import get_conversation_db

conv_db = get_conversation_db()
history = conv_db.get_conversation_history(user_id, server_id)
conv_db.add_message(user_id, server_id, "user", user_message)
conv_db.add_message(user_id, server_id, "assistant", response)
```

### Queue System Integration
**Future**: Queue system will load conversation history before processing requests and store results after completion.

## Performance Considerations

### Query Optimization
- **Primary Index**: `(user_id, server_id)` covers most common queries
- **Chronological**: `timestamp` index for ordering and time-based queries
- **Session Queries**: Dedicated index for session-based operations

### Memory Management
- **Connection Pooling**: Context manager ensures proper connection cleanup
- **Lazy Loading**: Database created only when first accessed
- **Batch Operations**: Single connection per operation with proper transaction handling

### Storage Efficiency
- **Minimal Schema**: Only essential fields for conversation tracking
- **Text Compression**: SQLite's built-in compression for text content
- **Cleanup Tools**: Built-in methods for removing old conversations

## Data Flow

### Message Storage Flow
```
Discord DM → DMAssistant → ConversationDatabase.add_message() → SQLite
```

### Context Loading Flow
```
Queue Request → ConversationDatabase.get_conversation_history() → DMAssistant Context
```

### History Management Flow
```
!clear-conversation-history → ConversationDatabase.clear_user_conversation_history()
```

## Security & Privacy

### Data Isolation
- **Server Boundaries**: All queries require server_id parameter
- **User Boundaries**: All queries require user_id parameter
- **No Cross-Leakage**: Impossible to access other users' or servers' data

### Data Retention
- **Manual Cleanup**: Users can clear their own history with commands
- **Automated Cleanup**: Built-in methods for old message removal
- **No Sensitive Data**: Only conversation content stored, no Discord tokens/secrets

### Error Security
- **No Data Exposure**: Error messages don't leak conversation content
- **Safe Defaults**: Failed operations return empty results rather than errors
- **Logging Privacy**: Error logs contain identifiers but not message content

## Testing Strategy

### Unit Tests Coverage
- **Database Operations**: All CRUD operations tested
- **Server Isolation**: Cross-server data leakage prevention
- **User Isolation**: Cross-user data leakage prevention  
- **Conversation Flow**: Multi-turn conversation scenarios
- **Error Handling**: Invalid inputs and constraint violations
- **Concurrent Access**: Thread safety validation

### Test Database
- **Isolation**: Temporary databases for each test
- **Cleanup**: Automatic test database removal
- **Realistic Data**: Representative conversation scenarios

## Migration and Upgrades

### Schema Versioning
**Current**: Initial schema v1.0
**Future**: Schema versioning system for database migrations

### Backward Compatibility
- **Nullable Fields**: New optional fields added as nullable
- **Index Creation**: New indexes added with `IF NOT EXISTS`
- **Data Migration**: Scripts for schema changes without data loss

## Monitoring and Maintenance

### Database Statistics
```python
stats = conv_db.get_database_stats()
# Returns: total_messages, unique_users, unique_servers, messages_today
```

### Health Checks
- **Connection Test**: Database accessibility validation
- **Schema Verification**: Table and index existence checks
- **Data Integrity**: Constraint validation and orphaned record detection

### Cleanup Operations
```python
# Remove conversations older than 30 days
deleted_count = conv_db.cleanup_old_conversations(days=30)
```

## Future Enhancements

### Phase 2+ Features
- **Advanced Session Management**: Enhanced session tracking with timeouts
- **Conversation Analytics**: User engagement and usage statistics
- **Export/Import**: Conversation backup and restoration
- **Search Integration**: Full-text search within conversation history
- **Compression**: Large conversation history compression

### Performance Optimizations
- **Connection Pooling**: Reusable connection pool for high-traffic scenarios
- **Bulk Operations**: Batch insert/update operations for queue processing
- **Read Replicas**: Read-only database replicas for heavy query loads
- **Caching Layer**: In-memory caching for frequently accessed conversations

## Configuration

### Database Location
**Default**: `src/db/databases/conversations.sqlite3`
**Customizable**: Path can be overridden during ConversationDatabase initialization

### Connection Settings
- **Timeout**: 30 seconds for database operations
- **Threading**: `check_same_thread=False` with proper locking
- **Row Factory**: `sqlite3.Row` for named column access

### Logging
- **Module Logger**: `logging.getLogger(__name__)`
- **Log Levels**: Info for operations, Debug for details, Error for failures
- **Context**: All log messages include user_id and server_id for traceability