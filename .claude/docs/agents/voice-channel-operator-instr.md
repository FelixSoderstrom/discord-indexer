# Voice-Channel-Operator Agent Instructions

## Key Areas of Focus
- `src/bot/voice_handler.py` - Core VoiceChannelManager class and all voice operations
- `src/db/conversation_db.py` - Voice sessions table and CRUD operations
- `src/bot/actions.py` - Voice command handler and voice state event listener
- `src/ai/agents/queue_worker.py` - Voice request processing in queue
- `src/ai/agents/conversation_queue.py` - ConversationRequest dataclass and queue management
- `src/cleanup.py` - Voice cleanup during shutdown
- `src/config/settings.py` - Voice feature configuration (ENABLE_VOICE_FEATURES, VOICE_TIMEOUT)
- `_ignore/phase.md` - Phase 1 requirements and testing checklist
- `_ignore/TTS_STT_Implementation_Guide.md` - Overall TTS/STT implementation roadmap

## Specific Responsibilities

### Voice Channel Lifecycle Management
- **Create** private voice channels with proper permissions for requesting user
- **Join** voice channels using Discord.py voice client and validate connection
- **Delete** voice channels when sessions end through any path (timeout, user leave, command)
- **Track** channel ownership and association with database sessions
- **Validate** bot has required permissions (CONNECT, SPEAK, MANAGE_CHANNELS) before operations

### Session Tracking and Database Operations
- **Create** voice session records with channel_id, user_id, guild_id, and created_at timestamp
- **Update** session records with ended_at timestamp on all cleanup paths
- **Query** active sessions for timer management and cleanup operations
- **Ensure** database consistency between channel state and session records
- **Prevent** orphaned sessions without proper end timestamps

### Timer Coordination and Cleanup
- **Monitor** 60-second timeout for user to join created voice channel
- **Trigger** automatic cleanup when timeout expires without user joining
- **Coordinate** timer cancellation when user successfully joins
- **Handle** race conditions between user join events and timer expiry
- **Log** all timer events with channel IDs and timestamps for debugging

### Voice State Event Handling
- **Process** on_voice_state_update events for user joins and leaves
- **Detect** when requesting user joins their created voice channel
- **Trigger** cleanup when last user leaves a bot-managed voice channel
- **Distinguish** between bot voice state changes and user voice state changes
- **Update** internal state tracking based on voice events

### Error Recovery and Orphaned Channel Cleanup
- **Catch** specific Discord.py exceptions (HTTPException, NotFound, Forbidden)
- **Recover** from Discord cache issues where get_channel() returns None
- **Clean up** orphaned channels on bot startup using database session queries
- **Handle** permission errors on Server #2 and log for investigation
- **Ensure** all error paths still update database and attempt cleanup

### Queue Integration
- **Process** voice requests from conversation queue system
- **Send** completion signals back to queue after channel operations
- **Coordinate** with queue worker for asynchronous voice operations
- **Maintain** single active voice session at a time (GPU constraint)
- **Signal** errors to queue system for proper request handling

## Coordination Boundaries
- **Works WITH conversation-queue-manager**: Receives voice requests via queue system
- **Works WITH discord-bot-operator**: Processes Discord voice state events
- **Works WITH db-manager**: Maintains voice session records in SQLite database
- **Provides TO users**: Private voice channels for TTS/STT interaction
- **Provides TO queue system**: Completion/error signals for voice requests
- **Provides TO database**: Session records with timestamps and metadata
- **Receives FROM queue_worker**: Voice channel creation requests
- **Receives FROM Discord events**: Voice state updates for join/leave detection
- **Receives FROM config**: Voice feature flags and timeout settings
- **Does NOT**: Handle audio processing, TTS/STT functionality (Phase 2), or multiple concurrent sessions

## Database Schema

### voice_sessions Table
```sql
CREATE TABLE IF NOT EXISTS voice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME DEFAULT NULL
)
```

**Key Points:**
- Active sessions have `ended_at = NULL`
- Ended sessions have `ended_at = CURRENT_TIMESTAMP`
- Query active sessions using `WHERE ended_at IS NULL`
- Always store guild_id for robust channel deletion

## Implementation Process

### 1. Analysis Phase
- Read voice_handler.py to understand current VoiceChannelManager implementation
- Review database schema for voice_sessions table structure
- Check actions.py for command handler and event listener integration
- Identify existing patterns for async Discord operations
- Examine current error handling and logging approaches
- Review Phase 1 requirements in _ignore/phase.md

### 2. Planning Phase
- Design approach considering async/await patterns for Discord.py
- Map out all cleanup paths (timeout, user leave, explicit close, shutdown)
- Plan database transaction ordering to avoid session retrieval issues
- Consider edge cases: permission errors, network drops, bot restarts
- Identify logging points for debugging timer and cleanup operations
- Verify PyNaCl dependency for voice operations

### 3. Implementation Phase
- Follow Singleton pattern for VoiceChannelManager class
- Use absolute imports from src.* modules (never relative imports)
- Apply type annotations using Typing library for all methods
- Implement specific exception handling (never catch broad Exception)
- Ensure database session updates occur after all Discord operations
- Add comprehensive logging with channel IDs and user IDs

### 4. Testing Phase
- Verify PyNaCl is installed correctly for voice dependencies
- Manually test voice channel creation with !voice command
- Test 60-second timeout expires correctly and cleans up
- Test user join within timeout cancels timer properly
- Test user leave after join triggers cleanup
- Validate no orphaned channels remain after each test
- Check database for proper created_at and ended_at timestamps
- Test on both Server #1 and Server #2 for permission differences

### 5. Validation Phase
- Confirm all cleanup paths update database sessions
- Verify no channels remain without corresponding active sessions
- Check logs for any silent failures in cleanup operations
- Validate timer precision is within ±1 second of 60s timeout
- Ensure channel creation completes in under 2 seconds
- Test bot restart properly cleans up pre-existing sessions

## Testing Procedures

### Manual Testing Checklist (Phase 1 Requirements)
1. **Basic Channel Creation**:
   - Run `!voice` command in Server #1
   - Verify private voice channel created with bot joined
   - Verify only requesting user can see channel
   - Confirm database session created with created_at timestamp

2. **60-Second Timeout Test**:
   - Run `!voice` and DO NOT join channel
   - Wait 60 seconds
   - Verify channel is automatically deleted
   - Verify database session has ended_at timestamp
   - Check logs for timer expiry event

3. **User Join Within Timeout**:
   - Run `!voice` and join within 60 seconds
   - Verify bot remains connected
   - Verify timer was cancelled (check logs)
   - Session should remain active (no ended_at)

4. **User Leave Cleanup**:
   - Create channel and join
   - Leave the channel as the user
   - Verify channel is deleted within 1 second
   - Verify database session ended
   - Confirm bot disconnected properly

5. **Explicit Close Command** (if implemented):
   - Create channel and join
   - Use close command
   - Verify immediate cleanup
   - Check database session ended

6. **Bot Restart Cleanup**:
   - Create voice channel
   - Restart bot without cleaning up
   - Verify orphaned sessions are cleaned on startup
   - Check cleanup.py logs for voice cleanup operations

7. **Permission Testing on Server #2**:
   - Attempt `!voice` on Server #2
   - Document any permission errors
   - Verify error handling provides clear user feedback

### Performance Validation
- Channel creation: Measure time from command to bot join (target: < 2s)
- Cleanup speed: Measure time from trigger to channel deletion (target: < 1s)
- Timer precision: Verify timeout occurs at 60s ±1s
- Session queries: Ensure database operations don't block event loop

### Log Verification
- All channel creations logged with channel_id and user_id
- All timer starts and cancellations logged
- All cleanup triggers logged with reason (timeout/leave/close)
- All errors logged with specific exception types and context

## Voice Operation Patterns

### Creating a Voice Channel
```python
# Pattern used in voice_handler.py
channel = await guild.create_voice_channel(
    name=f"Voice-{user.name}",
    category=target_category,
    overwrites={
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, connect=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, connect=True)
    }
)
```

### Joining Voice Channel
```python
# Pattern for bot connection
voice_client = await channel.connect(timeout=10.0, reconnect=True)
# Store voice_client reference in manager state
```

### Timer Management
```python
# Pattern for timeout handling
asyncio.create_task(self._channel_timeout_handler(channel.id, user.id, 60))
# Timer should be cancellable via stored task reference
# Cancel on user join event
```

### Cleanup Ordering Principle
**CRITICAL: Always follow this cleanup order to prevent data loss:**
```python
# 1. Retrieve session data FIRST (before any operations that might invalidate it)
session = self.db.get_active_session_by_channel(str(channel_id))
guild_id = int(session['guild_id']) if session.get('guild_id') else None
user_id = session.get('user_id')

# 2. Cancel timers
self.cancel_timer(channel_id)

# 3. Disconnect bot from voice
await voice_client.disconnect()

# 4. Delete Discord channel
await self.ensure_channel_deleted(channel_id, guild_id)

# 5. Free queue slot (requires user_id)
await queue.complete_request(request, success=True)

# 6. End database session (LAST step - after all operations complete)
self.db.end_voice_session(session_id)
```

**Why This Order Matters:**
- Retrieve data FIRST because ending session invalidates queries
- End session LAST to keep data available for all cleanup operations
- Queue slot freeing requires user_id from session
- Channel deletion may need guild_id from session

### Robust Channel Deletion Pattern (ensure_channel_deleted)
The `ensure_channel_deleted()` method implements a multi-method approach to handle Discord cache issues:

```python
async def ensure_channel_deleted(self, channel_id: int, guild_id: int) -> bool:
    """Ensure a voice channel is deleted using all available methods.

    Returns:
        True if channel was deleted or doesn't exist, False if deletion failed
    """
    guild = self.bot.get_guild(guild_id)

    # Method 1: Try to get from cache
    channel = guild.get_channel(channel_id)

    # Method 2: If not in cache, fetch from API
    if not channel:
        try:
            channel = await guild.fetch_channel(channel_id)
        except discord.NotFound:
            # Channel doesn't exist, that's fine
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch channel {channel_id}: {e}")
            return False

    # Delete the channel
    if channel:
        try:
            await channel.delete(reason="Voice session cleanup")
            return True
        except discord.HTTPException as e:
            logger.error(f"Failed to delete channel {channel_id}: {e}")
            return False

    return True
```

**Key Concepts:**
- Fallback chain: cache → API fetch → graceful failure
- NotFound is success (channel already gone)
- Requires guild_id to fetch from API
- Always returns boolean for caller feedback

## Integration Points

### Queue System Integration
- Voice requests come through `queue_worker.py` process_voice_request()
- ConversationRequest dataclass in `conversation_queue.py` has `request_type` field ("ask" or "voice")
- Manager must call `mark_voice_request_completed()` on success via `queue.complete_request()`
- Manager must call appropriate error signaling on failure
- Single active session constraint enforced at queue level
- `status_message_id` field in ConversationRequest is used for user feedback updates

### Database Integration
- Session creation: `create_voice_session(channel_id, user_id, guild_id)`
- Session ending: `end_voice_session(session_id)`
- Active session by user: `get_active_session_by_user(user_id)`
- Active session by channel: `get_active_session_by_channel(channel_id)`
- All active sessions: `get_all_active_sessions()`
- All functions handle SQLite errors gracefully and return None on failure

### Discord Event Integration
- `on_voice_state_update` in actions.py handles join/leave detection
- Event listener determines if state change is for bot-managed channel
- Triggers cleanup_channel() when appropriate
- Must distinguish bot events from user events

### Configuration Integration
- `ENABLE_VOICE_FEATURES`: Master switch for voice functionality
- `VOICE_TIMEOUT`: Configurable timeout duration (default 60s)
- Settings loaded from environment via settings.py

## Security and Permissions

### Required Discord Permissions
- MANAGE_CHANNELS: For creating and deleting voice channels
- CONNECT: For bot to join voice channels
- SPEAK: For future audio playback (Phase 2)
- VIEW_CHANNEL: For bot to see created channels

### Permission Validation
- Check bot permissions before attempting channel creation
- Provide clear error messages when permissions are insufficient
- Log permission errors with guild ID for administrator investigation

### Privacy Considerations
- Voice channels are private (only user and bot can see)
- Channel names include username for user identification
- Session data includes user_id for tracking and cleanup

## Performance Considerations

### Hardware Constraints
- RTX 3090 GPU with 24GB RAM
- Single voice session at a time due to GPU constraints
- Future TTS/STT processing will use same GPU

### Optimization Targets
- Channel creation < 2 seconds (network-dependent)
- Cleanup operations < 1 second
- Timer precision ±1 second
- Database operations should not block event loop (use proper async patterns)

### Resource Management
- Voice clients must be properly disconnected to free resources
- Channels must be deleted to avoid Discord clutter
- Database connections should use connection pooling
- Timer tasks should be properly cancelled to avoid memory leaks

## Documentation Requirements

### Code Documentation
- Use Google Docstring format for all methods
- Document all parameters with types
- Document return values and exceptions
- Include usage examples for complex operations

### Feature Documentation
- Update relevant documentation in `documentation/` directory after changes
- Document new voice features or configuration options
- Maintain accuracy of Phase 1 completion status in _ignore/phase.md

### Error Documentation
- Log all errors with sufficient context for debugging
- Document known workarounds in code comments
- Maintain clear error messages for user-facing issues

## Standards Compliance

### Python Standards
- Follow Zen of Python principles
- Use type annotations from Typing library
- Python 3.10.6 compatibility required

### Import Standards
- ALWAYS use absolute imports: `from src.bot.voice_handler import VoiceChannelManager`
- NEVER use relative imports: `from ..bot.voice_handler import VoiceChannelManager`
- Import at top of file, never inside conditionals

### Error Handling Standards
- Catch specific exceptions only (HTTPException, NotFound, Forbidden)
- NEVER catch broad Exception (violates project standards)
- Always log errors using the logger

### Code Quality Standards
- NO emojis in code or comments
- Clear, descriptive variable names
- Maintain separation of concerns across modules

## Async/Await Best Practices

### Discord.py Patterns
- All Discord API calls are async and must be awaited
- Use `asyncio.create_task()` for background operations like timers
- Never block the event loop with synchronous operations
- Use proper timeout parameters for network operations

### Error Handling in Async Context
- Use try/except blocks within async functions
- Handle ClientException for voice client errors
- Handle HTTPException for Discord API errors
- Properly clean up resources in finally blocks

### Task Management
- Store timer task references for cancellation
- Cancel tasks properly when user joins
- Avoid creating orphaned tasks that never complete
- Use asyncio.gather() for parallel operations when appropriate
