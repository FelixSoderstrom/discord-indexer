# Conversation Queue Manager Agent Instructions

## Key Areas of Focus
- `src/ai/agents/conversation_queue.py` - The main queue implementation
- `src/ai/agents/queue_worker.py` - Queue processing worker
- `src/bot/actions.py` - Discord command integration and bot event handlers
- `src/db/conversation_db.py` - Database persistence for conversation history

## Specific Responsibilities
### Discord DM Request Queue Management
- Stateless conversation request queuing via `!ask` commands
- Anti-spam protection (one active request per user)
- Queue depth monitoring and capacity management (default: 50 requests)
- Fair FIFO processing with position tracking
- Real-time Discord status message updates

### Single Worker Process Coordination
- Async worker loop managing continuous request processing
- LangChain DMAssistant integration for LLM processing
- Request timeout handling (60-second limits)
- Graceful worker startup/shutdown with bot lifecycle
- Error recovery with user notifications via Discord

### Discord Integration and Message Processing
- Discord command parsing and server selection handling
- Real-time status message editing and user feedback
- Integration with bot event handlers in `src/bot/actions.py`
- Discord channel management for response delivery
- Multi-server support with server selection workflow

### Database Integration and Persistence
- Conversation logging to ConversationDB for both user and assistant messages
- Request state tracking (QUEUED → PROCESSING → COMPLETED/FAILED)
- Server context management (server_id or "0" for DMs)
- Error response logging for timeout and processing failures
- Integration with ChromaDB for server message search context

## Coordination Boundaries
- **Works WITH LangChain DMAssistant**: Queues requests but does NOT implement LLM logic or tool selection
- **Works WITH Discord Bot Client**: Integrates with bot commands/events but does NOT manage bot lifecycle
- **Works WITH ConversationDB**: Logs conversations but does NOT manage database schema or connection management
- **Works WITH ChromaDB Integration**: Provides server context but does NOT handle message indexing or search implementation
- **Does NOT**: Handle Discord message indexing (message pipeline responsibility)
- **Does NOT**: Implement LLM agents or tool logic (DMAssistant responsibility)
- **Does NOT**: Manage Discord bot connection or event routing (bot client responsibility)

## Implementation Process
1. **Analysis Phase**: Examine Discord integration patterns and current queue implementation
2. **Planning Phase**: Design anti-spam protection and request flow architecture
3. **Implementation Phase**: Build queue system with Discord status updates and database logging
4. **Integration Phase**: Connect with LangChain DMAssistant and Discord bot commands
5. **Monitoring Phase**: Implement statistics tracking and error handling

## Testing Approach
**Note**: Currently no project-specific automated tests exist in the codebase.

**Manual Testing Strategy**:
- Test Discord `!ask` command integration with various message formats
- Verify anti-spam protection by attempting multiple simultaneous requests
- Test queue capacity limits and graceful rejection handling
- Validate worker timeout handling (60-second limits) and error responses
- Test real-time Discord status message updates during processing
- Verify database logging for both successful and failed requests
- Test server selection workflow with multi-server users
- Focus on queue fairness and FIFO processing order

**Recommended Test Creation**:
- Unit tests for ConversationQueue class methods
- Integration tests for Discord command → queue → worker flow
- Mock tests for LangChain DMAssistant integration
- Database persistence validation tests