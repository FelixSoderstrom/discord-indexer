# src/llm/agents/dm_assistant.py Documentation

## Purpose
Discord DM Assistant agent with conversation memory and context management. Provides personalized, context-aware responses to Discord direct messages while maintaining conversation history and proper Discord formatting.

## What It Does
1. **Conversation Management**: Maintains per-user conversation history and context
2. **Discord Integration**: Handles Discord-specific message formatting and length limits
3. **Context Window Management**: Automatically manages conversation length and memory
4. **Prompt Engineering**: Loads and manages system prompts from JSON configuration
5. **Response Generation**: Coordinates with chat completion API for response generation

## Core Data Structures

### `MessageContext` Dataclass
```python
@dataclass
class MessageContext:
    content: str                    # Message text content
    author: str                     # Author username
    channel: str                    # Channel name
    timestamp: datetime             # Message timestamp
    message_id: str                 # Discord message ID
    similarity_score: float = 0.0   # Similarity score for search results
```

## Main Class: `DMAssistant`

### Initialization Parameters
- **`model_name`**: Ollama model name (defaults to settings configuration)
- **`temperature`**: Generation creativity (defaults to environment/0.7)
- **`max_response_length`**: Discord character limit (defaults to 1800)
- **`max_context_messages`**: Maximum conversation history (defaults to 20)

### Instance Attributes
```python
self.conversations: Dict[str, List[Dict[str, str]]]  # Per-user conversation storage
self.system_prompt: str                              # Loaded system prompt
self.model_name: str                                 # Model configuration
self.temperature: float                              # Generation parameters
self.max_response_length: int                        # Discord formatting limits
self.max_context_messages: int                       # Memory management
```

## Key Methods

### Conversation Management

**`respond_to_dm(message, user_id, user_name=None)`**
- **Purpose**: Main entry point for processing Discord DM responses
- **Parameters**:
  - `message`: User's message content
  - `user_id`: Discord user ID for conversation tracking
  - `user_name`: Optional display name for logging
- **Returns**: Generated response text (Discord-formatted and length-limited)
- **Process**:
  1. Builds conversation context with history
  2. Calls chat completion API with structured messages
  3. Handles response formatting and truncation
  4. Updates conversation history with both messages
  5. Logs interaction metrics

**`clear_conversation(user_id)`**
- **Purpose**: Reset conversation history for specific user
- **Use Cases**: User requests fresh start, debugging, memory management

**`get_conversation_length(user_id)`**
- **Purpose**: Query current conversation message count
- **Returns**: Number of messages in user's conversation history

### Internal Methods

**`_load_system_prompt()`**
- **Purpose**: Loads system prompt from JSON configuration file
- **Fallback**: Uses default prompt if file loading fails
- **File Location**: `sys_prompts/dm_assistant.json`

**`_build_full_conversation(user_id, new_message)`**
- **Purpose**: Constructs complete message array for API call
- **Structure**: [system_prompt, conversation_history..., new_user_message]
- **Context Management**: Includes conversation history with proper formatting

**`_add_message_to_conversation(user_id, role, content)`**
- **Purpose**: Adds message to user's conversation history
- **Memory Management**: Automatically trims old messages when limit exceeded
- **Trimming Strategy**: Keeps system message + recent messages

**`_get_conversation_messages(user_id)`**
- **Purpose**: Retrieves conversation history for specific user
- **Initialization**: Creates empty conversation if user not found

### Utility Methods

**`health_check()`**
- **Purpose**: Validates agent and model availability
- **Returns**: Boolean indicating system health

**`get_stats()`**
- **Purpose**: Provides agent statistics and configuration
- **Returns**: Dictionary with conversation counts, model info, and limits

## Conversation Flow

### First Message from User
1. User sends message to Discord DM
2. `respond_to_dm()` called with user message
3. System prompt loaded from JSON
4. Conversation built: [system_prompt, user_message]
5. Chat completion API called
6. Response generated and formatted
7. Both messages added to conversation history

### Subsequent Messages
1. User sends follow-up message
2. `respond_to_dm()` called with new message
3. Full conversation built: [system_prompt, history..., new_message]
4. Chat completion API called with full context
5. Response generated with conversation awareness
6. Conversation history updated with new exchange

### Memory Management
1. Conversation grows with each exchange
2. When `max_context_messages` exceeded:
   - System prompt preserved (position 0)
   - Oldest messages removed from middle
   - Recent messages retained for context

## Configuration Management

### System Prompt Loading
```python
# Loads from: src/llm/agents/sys_prompts/dm_assistant.json
{
    "system_prompt": "You are a helpful Discord DM assistant..."
}
```

### Environment Configuration
- **`LLM_MODEL_NAME`**: Model name from settings
- **`LLM_TEMPERATURE`**: Generation temperature
- **`LLM_MAX_RESPONSE`**: Discord response length limit
- **`LLM_MAX_CONTEXT_MESSAGES`**: Conversation memory limit

## Discord Integration

### Response Formatting
- **Character Limit**: Automatically truncates responses > 1800 characters
- **Truncation Indicator**: Adds "*[Response truncated]*" when needed
- **Discord Markdown**: Supports **bold**, *italic*, and other Discord formatting
- **Line Breaks**: Preserves readable formatting for Discord display

### Error Handling
- **Model Failures**: Returns user-friendly error messages
- **API Errors**: Graceful degradation with helpful feedback
- **Configuration Issues**: Fallback prompts and settings

## Usage Examples

### Basic DM Response
```python
from llm.agents.dm_assistant import DMAssistant

# Initialize assistant
assistant = DMAssistant()

# Process user message
response = await assistant.respond_to_dm(
    message="Hello! How are you?",
    user_id="123456789",
    user_name="TestUser"
)

print(response)  # "Hi there! I'm doing well, thanks for asking..."
```

### Conversation Management
```python
# Check conversation length
length = assistant.get_conversation_length("123456789")
print(f"Conversation has {length} messages")

# Clear conversation if needed
assistant.clear_conversation("123456789")

# Get assistant statistics
stats = assistant.get_stats()
print(f"Managing {stats['active_conversations']} conversations")
```

## Current Implementation Status

**Conversation Management**: Fully implemented with per-user history
**Discord Integration**: Fully implemented with formatting and limits
**Configuration**: Fully implemented with JSON prompts and environment settings
**Memory Management**: Fully implemented with automatic trimming
**Error Handling**: Comprehensive error handling with user-friendly messages
**Chat Completion Integration**: Fully implemented using pure API functions

## Integration Points

### Dependencies
- `src/llm/chat_completion.py` - Uses `generate_completion_with_messages_async()`
- `src/llm/utils.py` - Uses `ensure_model_available()` and `health_check()`
- `src/config/settings.py` - Uses configuration settings
- `sys_prompts/dm_assistant.json` - Loads system prompt configuration

### Used By
- Discord bot event handlers for DM processing
- Test scripts for validation
- Future Discord integration modules

## Design Decisions

### Why Per-User Conversation Storage?
- **Personalization**: Each user gets individual conversation context
- **Privacy**: User conversations isolated from each other
- **Scalability**: Dictionary-based storage scales to many users
- **Memory Management**: Individual conversation limits prevent memory bloat

### Why JSON System Prompts?
- **Configurability**: Easy prompt modifications without code changes
- **Version Control**: Prompt changes tracked separately from code
- **A/B Testing**: Easy to test different prompt variations
- **Non-Technical Updates**: Prompts can be updated by non-developers

### Why Discord-Specific Formatting?
- **User Experience**: Responses properly formatted for Discord display
- **Character Limits**: Prevents message send failures
- **Platform Integration**: Leverages Discord's markdown support
- **Error Prevention**: Automatic truncation prevents API errors

## Future Extensibility

This agent architecture supports easy extension:
- **Advanced Memory**: Conversation summarization for long-term memory
- **User Preferences**: Per-user settings and customization
- **Rich Media**: Image and file processing capabilities
- **Integration Features**: Calendar, reminders, and external service integration
- **Multi-Modal**: Voice message processing and generation
- **Analytics**: Conversation analytics and user behavior insights
- **Personalization**: Learning user preferences and communication styles

## Performance Considerations
- **Memory Efficiency**: Conversation trimming prevents unbounded growth
- **Async Operations**: Non-blocking response generation
- **Model Caching**: Reuses model instances across conversations
- **Prompt Caching**: System prompts loaded once and cached
- **Scalability**: Dictionary-based storage scales to thousands of users
