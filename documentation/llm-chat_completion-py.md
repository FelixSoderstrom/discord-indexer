# src/llm/chat_completion.py Documentation

## Purpose
Pure LLM API interface providing stateless chat completion functions. Acts as a reusable API layer for all agents, similar to OpenAI's API pattern, with no agent-specific logic or context management.

## What It Does
1. **Stateless Chat Completions**: Provides pure function-based LLM inference
2. **Multiple Input Formats**: Supports both string prompts and structured message arrays
3. **Async/Sync Operations**: Offers both asynchronous and synchronous completion methods
4. **Response Metadata**: Returns detailed response information including tokens and timing
5. **Configuration Management**: Uses centralized settings with environment fallbacks

## Core Data Structures

### `LLMResponse` Dataclass
```python
@dataclass
class LLMResponse:
    content: str           # Generated response text
    tokens_used: int       # Total tokens consumed (prompt + completion)
    response_time: float   # Generation time in seconds
    model_used: str        # Model name used for generation
    success: bool          # Whether generation succeeded
    error: str = None      # Error message if generation failed
```

## Core Functions

### String-Based Completions

**`generate_completion_sync(prompt, model_name, temperature, max_tokens)`**
- **Purpose**: Synchronous chat completion from raw text prompt
- **Input**: Single string containing full conversation context
- **Output**: `LLMResponse` with generated content and metadata
- **Use Case**: Simple prompts or pre-formatted conversation strings

**`generate_completion_async(prompt, model_name, temperature, max_tokens)`**
- **Purpose**: Asynchronous version using thread executor
- **Input**: Same as sync version
- **Output**: Same as sync version
- **Use Case**: Non-blocking operations in async contexts

### Message-Based Completions

**`generate_completion_with_messages_sync(messages, model_name, temperature, max_tokens)`**
- **Purpose**: Synchronous completion from structured message array
- **Input**: List of message dictionaries with 'role' and 'content' keys
- **Output**: `LLMResponse` with generated content and metadata
- **Use Case**: Structured conversations with proper role separation

**`generate_completion_with_messages_async(messages, model_name, temperature, max_tokens)`**
- **Purpose**: Asynchronous version using thread executor
- **Input**: Same as sync version
- **Output**: Same as sync version
- **Use Case**: Agent conversation management with async coordination

## Message Format

### Expected Message Structure
```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
    {"role": "user", "content": "How are you?"}
]
```

### Supported Roles
- **system**: System instructions and behavior guidelines
- **user**: User messages and queries
- **assistant**: Previous assistant responses for context

## Configuration

### Parameter Defaults
- **`model_name`**: Uses `settings.LLM_MODEL_NAME` from configuration
- **`temperature`**: Uses `LLM_TEMPERATURE` environment variable (default: 0.7)
- **`max_tokens`**: Default 500 tokens for response generation

### Ollama Generation Options
```python
options = {
    "temperature": temperature,      # Creativity/randomness (0.0-1.0)
    "num_predict": max_tokens,      # Maximum response tokens
    "top_p": 0.9,                   # Nucleus sampling parameter
    "repeat_penalty": 1.1           # Repetition penalty
}
```

## Error Handling

### Exception Types Handled
- **ConnectionError**: Ollama service connection issues
- **TimeoutError**: Generation timeout errors
- **OSError**: System-level errors
- **ValueError**: Invalid parameters or model names
- **KeyError**: Missing response fields
- **RuntimeError**: General Ollama runtime errors

### Error Response Format
```python
LLMResponse(
    content="",
    tokens_used=0,
    response_time=actual_time,
    model_used=model_name,
    success=False,
    error=str(exception)
)
```

## Usage Examples

### Simple String Completion
```python
from llm.chat_completion import generate_completion_sync

response = generate_completion_sync(
    prompt="Hello, how are you?",
    model_name="llama3.2",
    temperature=0.7
)

if response.success:
    print(response.content)
```

### Structured Conversation
```python
from llm.chat_completion import generate_completion_with_messages_async

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain quantum physics"}
]

response = await generate_completion_with_messages_async(messages)
print(f"Generated in {response.response_time:.2f}s using {response.tokens_used} tokens")
```

## Integration Pattern

### Agent Integration
```python
class MyAgent:
    async def respond(self, user_message: str) -> str:
        # Agent builds conversation context
        messages = self.build_conversation_context(user_message)
        
        # Call pure API function
        response = await generate_completion_with_messages_async(messages)
        
        # Agent handles response
        if response.success:
            self.update_conversation_history(response.content)
            return response.content
        else:
            return "Sorry, I encountered an error."
```

## Current Implementation Status

**Core Functions**: Fully implemented with comprehensive error handling
**Async Support**: Fully implemented using thread executors
**Configuration**: Fully implemented with settings integration
**Response Metadata**: Fully implemented with detailed tracking
**Error Handling**: Comprehensive exception handling with detailed logging

## Design Decisions

### Why Function-Based API?
- **Stateless**: No instance state to manage
- **Reusable**: Same functions work for any agent
- **Simple**: Direct function calls like OpenAI API
- **Testable**: Easy to unit test individual functions

### Why Both String and Message Formats?
- **Flexibility**: Different agents have different needs
- **Legacy Support**: Simple string prompts for basic use cases
- **Advanced Features**: Structured messages for complex conversations
- **OpenAI Compatibility**: Message format matches OpenAI patterns

### Why Sync and Async Versions?
- **Blocking Operations**: Some contexts require synchronous calls
- **Non-blocking Operations**: Async contexts need non-blocking functions
- **Thread Safety**: Async versions use thread executors for Ollama calls
- **Performance**: Async enables concurrent agent operations

## Integration Points

### Used By
- `src/llm/agents/dm_assistant.py` - Uses message-based async functions
- All future LLM agents - Reusable across entire system
- Test scripts and utilities

### Dependencies
- `src/llm/utils.py` - Uses `get_ollama_client()` for API calls
- `src/config/settings.py` - Uses configuration settings
- `ollama` package for model inference

## Future Extensibility

This API layer is designed for easy extension:
- **Streaming Responses**: Add streaming completion functions
- **Batch Processing**: Support multiple completions in single call
- **Custom Parameters**: Additional Ollama generation parameters
- **Model Switching**: Dynamic model selection per request
- **Response Caching**: Cache frequent responses for performance
- **Alternative Backends**: Support for other LLM providers (OpenAI, Anthropic)
- **Advanced Features**: Function calling, tool usage, multimodal inputs

## Performance Considerations
- **Thread Executors**: Async functions use thread pools for blocking Ollama calls
- **Resource Management**: No persistent connections or state
- **Memory Efficiency**: Minimal memory footprint per call
- **Concurrent Usage**: Thread-safe for multiple simultaneous calls
- **Response Timing**: Detailed timing metadata for performance monitoring
