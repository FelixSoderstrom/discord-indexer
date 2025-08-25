# LLM Integration Documentation
## Discord Bot Indexing Project

### Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup and Installation](#setup-and-installation)
4. [Core Components](#core-components)
5. [Implementation Guide](#implementation-guide)
6. [Configuration](#configuration)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)
11. [Sprint Integration](#sprint-integration)

---

## Overview

The LLM Integration module provides a complete solution for generating contextual responses to Discord user queries using locally hosted Llama 3.2 3B via Ollama. This module is designed specifically for the Discord Bot Indexing Project and handles:

- **Context Formatting**: Converting ChromaDB search results into LLM-friendly context
- **Response Generation**: Using Llama 3.2 3B to generate conversational responses
- **Discord Optimization**: Ensuring responses fit Discord's character limits and formatting
- **Performance Management**: Async/sync operations with built-in monitoring
- **Error Resilience**: Comprehensive error handling and fallback mechanisms

### Key Design Principles

- **Modularity**: Self-contained class that integrates easily with existing FastAPI/Discord.py architecture
- **Performance**: Optimized for 8GB VRAM with fast response times (<5 seconds target)
- **Discord-Native**: Built specifically for Discord's formatting and limitations
- **Production-Ready**: Includes logging, monitoring, and error handling

---

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Discord Bot   │    │   FastAPI API    │    │  DiscordLLM     │
│                 │    │                  │    │   Handler       │
│ - User Query    ├────► - Route Handler  ├────► - Context       │
│ - DM Interface  │    │ - ChromaDB Query │    │   Formatting    │
│                 │◄───┤ - Response       │◄───┤ - LLM Generation│
└─────────────────┘    │   Formatting     │    │ - Discord       │
                       └──────────────────┘    │   Optimization  │
                                               └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │     Ollama      │
                                               │  Llama 3.2 3B   │
                                               │                 │
                                               └─────────────────┘
```

### Data Flow

1. **User Query**: User sends message to Discord bot
2. **Semantic Search**: ChromaDB performs vector search for relevant messages
3. **Context Preparation**: `DiscordLLMHandler` formats retrieved messages
4. **LLM Generation**: Llama 3.2 3B generates response based on context
5. **Response Formatting**: Output formatted for Discord (character limits, markdown)
6. **Delivery**: Response sent back to user via Discord

---

## Setup and Installation

### Prerequisites

- Python 3.9+
- Ollama installed and running
- 8GB+ VRAM (RTX 3080/4070 or better recommended)
- ChromaDB already configured

### Installation Steps

#### 1. Install Ollama
```bash
# Download and install Ollama from https://ollama.ai
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve
```

#### 2. Download Llama 3.2 3B Model
```bash
# Pull the model (this will take some time)
ollama pull llama3.2:3b-instruct
```

#### 3. Install Python Dependencies
```bash
pip install ollama
```

#### 4. Verify Installation
```python
import ollama
client = ollama.Client()
response = client.chat(
    model='llama3.2:3b-instruct',
    messages=[{'role': 'user', 'content': 'Hello!'}]
)
print(response['message']['content'])
```

### Environment Variables

The handler reads configuration from environment variables with sensible defaults. Create a `.env` or set these in your environment:

```env
# Ollama connection (optional; defaults to http://localhost:11434)
OLLAMA_HOST=http://127.0.0.1:11434

# LLM configuration (all optional)
LLM_MODEL_NAME=llama3.2:3b-instruct     # default
LLM_MAX_CONTEXT=4000                    # default
LLM_MAX_RESPONSE=1800                   # default (Discord-safe)
LLM_TEMPERATURE=0.7                     # default
```

If you prefer code-based overrides, you can still pass parameters to `DiscordLLMHandler(...)`; explicit arguments take precedence over environment values.

---

## Core Components

### Data Classes

#### `MessageContext`
Represents a Discord message retrieved from ChromaDB.

```python
@dataclass
class MessageContext:
    content: str           # Message text content
    author: str           # Discord username
    channel: str          # Channel name
    timestamp: datetime   # When message was sent
    message_id: str       # Discord message ID
    similarity_score: float = 0.0  # ChromaDB similarity score
```

**Usage Example:**
```python
msg = MessageContext(
    content="Hey everyone, the server maintenance is scheduled for tomorrow",
    author="admin_user",
    channel="announcements",
    timestamp=datetime.now(),
    message_id="1234567890",
    similarity_score=0.85
)
```

#### `LLMResponse`
Contains the generated response and metadata.

```python
@dataclass
class LLMResponse:
    content: str          # Generated response text
    tokens_used: int      # Total tokens consumed
    response_time: float  # Generation time in seconds
    model_used: str       # Model identifier
    success: bool         # Whether generation succeeded
    error: Optional[str] = None  # Error message if failed
```

### Main Class: `DiscordLLMHandler`

#### Initialization Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_name` | str | `"llama3.2:3b-instruct"` | Ollama model identifier |
| `max_context_length` | int | `4000` | Maximum characters for context |
| `temperature` | float | `0.7` | Generation randomness (0.0-1.0) |
| `max_response_length` | int | `1800` | Max response chars for Discord |

#### Key Methods

##### `format_context_messages(messages: List[MessageContext]) -> str`
Converts ChromaDB search results into formatted context for the LLM.

**Input**: List of MessageContext objects
**Output**: Formatted string with Discord messages

**Example:**
```
[2024-01-15 14:30] john_doe in #general:
Does anyone know when the next event is?

---

[2024-01-15 15:45] admin_user in #announcements:
Next community event is scheduled for this weekend!
```

##### `generate_response_async(query: str, retrieved_messages: List[MessageContext]) -> LLMResponse`
Asynchronous response generation (recommended for Discord bots).

##### `generate_response_sync(query: str, retrieved_messages: List[MessageContext]) -> LLMResponse`
Synchronous response generation (for testing or simple integrations).

---

## Implementation Guide

### Basic Integration with FastAPI

```python
from fastapi import FastAPI, HTTPException
from discord_llm_handler import DiscordLLMHandler, MessageContext
import logging

app = FastAPI()
llm_handler = DiscordLLMHandler()  # uses env vars or defaults

@app.post("/generate_response")
async def generate_response(query: str, messages: List[dict]):
    try:
        # Convert dict messages to MessageContext objects
        contexts = [
            MessageContext(
                content=msg['content'],
                author=msg['author'],
                channel=msg['channel'],
                timestamp=datetime.fromisoformat(msg['timestamp']),
                message_id=msg['message_id'],
                similarity_score=msg.get('similarity_score', 0.0)
            )
            for msg in messages
        ]
        
        # Generate response
        response = await llm_handler.generate_response_async(query, contexts)
        
        return {
            "content": response.content,
            "success": response.success,
            "response_time": response.response_time,
            "tokens_used": response.tokens_used
        }
        
    except Exception as e:
        logging.error(f"Error in generate_response: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Discord Bot Integration

```python
import discord
from discord.ext import commands
from discord_llm_handler import DiscordLLMHandler
from chromadb_service import ChromaDBService  # Your ChromaDB integration

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
llm_handler = DiscordLLMHandler()
chromadb = ChromaDBService()

@bot.event
async def on_message(message):
    # Handle DMs to bot
    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        await handle_user_query(message)
    
    await bot.process_commands(message)

async def handle_user_query(message):
    try:
        # Get user query
        user_query = message.content.strip()
        
        # Search ChromaDB for relevant messages
        search_results = await chromadb.search(user_query, limit=10)
        
        # Convert to MessageContext objects
        retrieved_messages = [
            MessageContext(
                content=result.content,
                author=result.metadata['author'],
                channel=result.metadata['channel'],
                timestamp=datetime.fromisoformat(result.metadata['timestamp']),
                message_id=result.metadata['message_id'],
                similarity_score=result.similarity
            )
            for result in search_results
        ]
        
        # Generate response using LLM
        response = await llm_handler.generate_response_async(
            user_query, 
            retrieved_messages
        )
        
        if response.success:
            await message.channel.send(response.content)
            
            # Log performance metrics
            logging.info(f"Query processed in {response.response_time:.2f}s, "
                        f"{response.tokens_used} tokens used")
        else:
            await message.channel.send(
                "Sorry, I'm having trouble processing your request right now. "
                "Please try again later."
            )
            logging.error(f"LLM generation failed: {response.error}")
            
    except Exception as e:
        logging.error(f"Error handling user query: {e}")
        await message.channel.send(
            "I encountered an error while processing your request."
        )

@bot.command(name='health')
async def health_check(ctx):
    """Check if LLM is responsive"""
    is_healthy = llm_handler.health_check()
    status = "✅ LLM is responsive" if is_healthy else "❌ LLM is not responding"
    await ctx.send(status)
```

### Advanced Integration with Caching

```python
from functools import lru_cache
import hashlib
import json

class CachedLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_cache = {}
    
    def _create_cache_key(self, query: str, messages: List[MessageContext]) -> str:
        """Create cache key from query and message content"""
        content_hash = hashlib.md5(
            (query + str([m.content for m in messages])).encode()
        ).hexdigest()
        return content_hash
    
    async def generate_response_async(self, query: str, retrieved_messages: List[MessageContext]) -> LLMResponse:
        # Check cache first
        cache_key = self._create_cache_key(query, retrieved_messages)
        
        if cache_key in self.response_cache:
            cached_response = self.response_cache[cache_key]
            logging.info("Returning cached response")
            return cached_response
        
        # Generate new response
        response = await super().generate_response_async(query, retrieved_messages)
        
        # Cache successful responses
        if response.success:
            self.response_cache[cache_key] = response
        
        return response
```

---

## Configuration

### Model Configuration

#### Recommended Settings for Different Use Cases

**High Quality (Default)**
```python
llm_handler = DiscordLLMHandler(
    model_name="llama3.2:3b-instruct",   # overrides env
    temperature=0.7,
    max_context_length=4000,
    max_response_length=1800
)
```

**Fast Responses**
```python
llm_handler = DiscordLLMHandler(
    temperature=0.5,
    max_context_length=2000,
    max_response_length=1000
)
```

**High Context (for complex queries)**
```python
llm_handler = DiscordLLMHandler(
    max_context_length=6000,
    max_response_length=1800
)
```

### Ollama Configuration

Edit `/etc/ollama/ollama.conf` or set environment variables:

```bash
# Increase context window
export OLLAMA_NUM_CTX=8192

# Optimize for your GPU
export OLLAMA_GPU_LAYERS=35

# Set memory limit
export OLLAMA_MAX_VRAM=7000000000  # 7GB
```

### System Prompt Customization

```python
def create_custom_system_prompt(self) -> str:
    return """You are the official Discord bot for [Your Server Name]. 
    
Your personality:
- Friendly and helpful community member
- Knows the server's history and culture
- Uses appropriate Discord slang and emojis
- References server-specific channels and events
    
Your capabilities:
- Answer questions based on server message history
- Provide context about past discussions
- Help users find information from previous conversations
    
Response guidelines:
- Keep responses under 1800 characters
- Use **bold** for emphasis
- Reference specific users and channels when relevant
- If unsure, acknowledge uncertainty rather than guessing"""
```

---

## Error Handling

### Common Error Scenarios

#### 1. Model Not Available
```python
try:
    llm_handler = DiscordLLMHandler()
except Exception as e:
    logging.error(f"Failed to initialize LLM: {e}")
    # Fallback: Use cached responses or simple keyword matching
```

#### 2. Generation Timeout
```python
import asyncio

async def generate_with_timeout(llm_handler, query, messages, timeout=10):
    try:
        response = await asyncio.wait_for(
            llm_handler.generate_response_async(query, messages),
            timeout=timeout
        )
        return response
    except asyncio.TimeoutError:
        return LLMResponse(
            content="Sorry, that query is taking too long to process.",
            tokens_used=0,
            response_time=timeout,
            model_used=llm_handler.model_name,
            success=False,
            error="Timeout"
        )
```

#### 3. VRAM Exhaustion
```python
def handle_vram_error(llm_handler):
    """Restart Ollama service if VRAM issues occur"""
    logging.warning("VRAM exhaustion detected, attempting restart...")
    try:
        os.system("ollama restart")
        time.sleep(10)
        return llm_handler.health_check()
    except:
        return False
```

### Graceful Degradation

```python
class ResilientLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_responses = [
            "I'm having trouble processing that request right now.",
            "Let me check the server history for that information...",
            "That's an interesting question! Try rephrasing it?"
        ]
    
    async def generate_response_with_fallback(self, query: str, messages: List[MessageContext]) -> str:
        response = await self.generate_response_async(query, messages)
        
        if response.success:
            return response.content
        else:
            # Log error and return fallback
            logging.error(f"LLM failed: {response.error}")
            return random.choice(self.fallback_responses)
```

---

## Performance Considerations

### Memory Management

#### VRAM Usage Monitoring
```python
import subprocess

def check_gpu_memory():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True)
        used, total = map(int, result.stdout.strip().split(', '))
        return used, total
    except:
        return None, None

# Check before generation
used, total = check_gpu_memory()
if used and used > 7000:  # More than 7GB used
    logging.warning(f"High VRAM usage: {used}MB/{total}MB")
```

#### Context Length Optimization
```python
def optimize_context_length(messages: List[MessageContext], max_length: int) -> List[MessageContext]:
    """Prioritize more recent and higher-scoring messages"""
    
    # Sort by recency and similarity
    scored_messages = []
    for msg in messages:
        # Weight: 70% similarity, 30% recency
        days_old = (datetime.now() - msg.timestamp).days
        recency_score = max(0, 1 - days_old / 30)  # Decay over 30 days
        combined_score = 0.7 * msg.similarity_score + 0.3 * recency_score
        scored_messages.append((combined_score, msg))
    
    # Sort by combined score
    scored_messages.sort(key=lambda x: x[0], reverse=True)
    
    # Add messages until context limit reached
    selected = []
    current_length = 0
    
    for score, msg in scored_messages:
        msg_length = len(f"[{msg.timestamp}] {msg.author}: {msg.content}\n")
        if current_length + msg_length <= max_length:
            selected.append(msg)
            current_length += msg_length
        else:
            break
    
    return selected
```

### Response Time Optimization

#### Batch Processing
```python
async def process_multiple_queries(llm_handler, queries_and_contexts):
    """Process multiple queries concurrently"""
    tasks = []
    for query, contexts in queries_and_contexts:
        task = llm_handler.generate_response_async(query, contexts)
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    return responses
```

#### Response Caching Strategy
```python
class SmartCache:
    def __init__(self, max_size=1000, ttl_seconds=3600):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[LLMResponse]:
        if key not in self.cache:
            return None
        
        # Check TTL
        if time.time() - self.timestamps[key] > self.ttl:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        return self.cache[key]
    
    def set(self, key: str, response: LLMResponse):
        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.timestamps.keys(), key=self.timestamps.get)
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
        
        self.cache[key] = response
        self.timestamps[key] = time.time()
```

---

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch
from discord_llm_handler import DiscordLLMHandler, MessageContext, LLMResponse
from datetime import datetime

@pytest.fixture
def llm_handler():
    return DiscordLLMHandler()

@pytest.fixture
def sample_messages():
    return [
        MessageContext(
            content="Hello everyone!",
            author="user1",
            channel="general",
            timestamp=datetime.now(),
            message_id="123",
            similarity_score=0.8
        ),
        MessageContext(
            content="How's everyone doing?",
            author="user2", 
            channel="general",
            timestamp=datetime.now(),
            message_id="124",
            similarity_score=0.7
        )
    ]

def test_context_formatting(llm_handler, sample_messages):
    """Test message context formatting"""
    formatted = llm_handler.format_context_messages(sample_messages)
    
    assert "user1" in formatted
    assert "Hello everyone!" in formatted
    assert "#general" in formatted
    assert "---" in formatted  # Message separator

def test_empty_context(llm_handler):
    """Test handling of empty message list"""
    formatted = llm_handler.format_context_messages([])
    assert "No relevant messages found" in formatted

@patch('ollama.Client')
def test_sync_response_generation(mock_client, llm_handler, sample_messages):
    """Test synchronous response generation"""
    
    # Mock Ollama response
    mock_client.return_value.chat.return_value = {
        'message': {'content': 'Test response'},
        'prompt_eval_count': 100,
        'eval_count': 50
    }
    
    response = llm_handler.generate_response_sync("Test query", sample_messages)
    
    assert response.success
    assert response.content == "Test response"
    assert response.tokens_used == 150
    assert response.response_time > 0

@pytest.mark.asyncio
@patch('ollama.Client')
async def test_async_response_generation(mock_client, llm_handler, sample_messages):
    """Test asynchronous response generation"""
    
    mock_client.return_value.chat.return_value = {
        'message': {'content': 'Async test response'},
        'prompt_eval_count': 80,
        'eval_count': 40
    }
    
    response = await llm_handler.generate_response_async("Async test", sample_messages)
    
    assert response.success
    assert "Async test response" in response.content

def test_response_truncation(llm_handler, sample_messages):
    """Test that long responses are truncated for Discord"""
    
    with patch.object(llm_handler, '_generate_sync_response') as mock_gen:
        # Mock a very long response
        long_content = "x" * 2000  # Longer than max_response_length
        mock_gen.return_value = {
            'message': {'content': long_content},
            'prompt_eval_count': 100,
            'eval_count': 100
        }
        
        response = llm_handler.generate_response_sync("test", sample_messages)
        
        assert len(response.content) <= llm_handler.max_response_length
        assert "*[Response truncated]*" in response.content

def test_health_check(llm_handler):
    """Test model health check"""
    with patch.object(llm_handler.client, 'chat') as mock_chat:
        mock_chat.return_value = {'message': {'content': 'OK'}}
        
        assert llm_handler.health_check() == True
        
        # Test failure case
        mock_chat.side_effect = Exception("Connection error")
        assert llm_handler.health_check() == False
```

### Integration Tests

```python
@pytest.mark.integration
class TestLLMIntegration:
    """Integration tests requiring actual Ollama service"""
    
    @pytest.fixture(scope="class")
    def real_llm_handler(self):
        """Use real LLM handler for integration tests"""
        return DiscordLLMHandler()
    
    def test_real_model_health(self, real_llm_handler):
        """Test actual model availability"""
        assert real_llm_handler.health_check()
    
    def test_real_response_generation(self, real_llm_handler, sample_messages):
        """Test actual response generation"""
        response = real_llm_handler.generate_response_sync(
            "What did the users say?", 
            sample_messages
        )
        
        assert response.success
        assert len(response.content) > 0
        assert response.response_time < 10  # Should be fast
        assert response.tokens_used > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, real_llm_handler, sample_messages):
        """Test handling multiple concurrent requests"""
        queries = ["Query 1", "Query 2", "Query 3"]
        
        tasks = [
            real_llm_handler.generate_response_async(q, sample_messages)
            for q in queries
        ]
        
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            assert response.success
            assert len(response.content) > 0
```

### Load Testing

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test_llm():
    """Simulate high load on LLM handler"""
    llm_handler = DiscordLLMHandler()
    
    sample_messages = [
        MessageContext(
            content=f"Test message {i}",
            author=f"user{i}",
            channel="test",
            timestamp=datetime.now(),
            message_id=str(i),
            similarity_score=0.5
        )
        for i in range(5)
    ]
    
    # Simulate 50 concurrent requests
    start_time = time.time()
    tasks = []
    
    for i in range(50):
        task = llm_handler.generate_response_async(
            f"Test query {i}", 
            sample_messages
        )
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()
    
    # Analyze results
    successful = sum(1 for r in responses if isinstance(r, LLMResponse) and r.success)
    failed = len(responses) - successful
    avg_time = sum(r.response_time for r in responses if isinstance(r, LLMResponse)) / successful
    
    print(f"Load test results:")
    print(f"Total time: {end_time - start_time:.2f}s")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Average response time: {avg_time:.2f}s")
    
    return successful >= 45  # 90% success rate

# Run load test
if __name__ == "__main__":
    result = asyncio.run(load_test_llm())
    print(f"Load test passed: {result}")
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "Model not found" Error
```
Error: model 'llama3.2:3b-instruct' not found
```

**Solution:**
```bash
# Check available models
ollama list

# Pull the model if missing
ollama pull llama3.2:3b-instruct

# Verify installation
ollama run llama3.2:3b-instruct "Hello"
```

#### 2. VRAM Out of Memory
```
Error: CUDA out of memory
```

**Solutions:**
```bash
# Reduce GPU layers
export OLLAMA_GPU_LAYERS=20

# Use smaller quantization
ollama pull llama3.2:3b-instruct-q4_0

# Reduce context window
export OLLAMA_NUM_CTX=4096
```

#### 3. Slow Response Times
**Symptoms:** Responses take >10 seconds

**Debug Steps:**
```python
# Check GPU utilization
nvidia-smi

# Monitor Ollama logs
ollama logs

# Test with minimal context
response = llm_handler.generate_response_sync("Hi", [])
```

**Solutions:**
- Reduce `max_context_length`
- Use GPU acceleration
- Implement response caching
- Consider smaller model (llama3.2:1b)

#### 4. Connection Errors
```
Error: Connection refused to localhost:11434
```

**Solutions:**
```bash
# Start Ollama service
ollama serve

# Check if port is in use
netstat -tlnp | grep 11434

# Try different host
export OLLAMA_HOST=http://127.0.0.1:11434
```

#### 5. Discord Character Limit Issues
**Symptoms:** Messages getting cut off

**Solution:**
```python
# Ensure proper truncation
if len(response.content) > 1900:  # Leave buffer
    response.content = response.content[:1850] + "...\n*[Message truncated]*"
```

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enhanced LLM handler with debug info
class DebugLLMHandler(DiscordLLMHandler):
    def generate_response_sync(self, query: str, retrieved_messages: List[MessageContext]) -> LLMResponse:
        logging.debug(f"Processing query: {query[:100]}...")
        logging.debug(f"Retrieved {len(retrieved_messages)} messages")
        
        context = self.format_context_messages(retrieved_messages)
        logging.debug(f"Context length: {len(context)} characters")
        
        response = super().generate_response_sync(query, retrieved_messages)
        
        logging.debug(f"Response generated: {response.success}")
        logging.debug(f"Tokens used: {response.tokens_used}")
        logging.debug(f"Response time: {response.response_time:.2f}s")
        
        return response
```

### Performance Monitoring

```python
class MonitoredLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'average_response_time': 0,
            'total_tokens_used': 0
        }
    
    async def generate_response_async(self, query: str, retrieved_messages: List[MessageContext]) -> LLMResponse:
        response = await super().generate_response_async(query, retrieved_messages)
        
        # Update metrics
        self.metrics['total_requests'] += 1
        if response.success:
            self.metrics['successful_requests'] += 1
        
        # Update running average
        prev_avg = self.metrics['average_response_time']
        n = self.metrics['total_requests']
        self.metrics['average_response_time'] = (prev_avg * (n-1) + response.response_time) / n
        
        self.metrics['total_tokens_used'] += response.tokens_used
        
        return response
    
    def get_metrics(self) -> dict:
        success_rate = self.metrics['successful_requests'] / max(1, self.metrics['total_requests'])
        return {
            **self.metrics,
            'success_rate': success_rate
        }
```

---

## Sprint Integration

### Sprint 3: LLM Integration & RAG Testing (Weeks 5-6)

#### Week 5 Tasks

**Day 1-2: Setup and Basic Integration**
```python
# 1. Install and configure Ollama
# Follow setup instructions above

# 2. Create basic integration test
from discord_llm_handler import DiscordLLMHandler

def test_basic_integration():
    handler = DiscordLLMHandler()
    assert handler.health_check()
    print("✅ LLM integration successful")

# 3. Test with sample ChromaDB data
def test_with_chromadb():
    # Assuming you have ChromaDB already set up
    from your_chromadb_service import ChromaDBService
    
    chromadb = ChromaDBService()
    llm_handler = DiscordLLMHandler()
    
    # Search for sample messages
    results = chromadb.search("test query", limit=5)
    
    # Convert to MessageContext objects
    messages = convert_chromadb_to_contexts(results)
    
    # Generate response
    response = llm_handler.generate_response_sync("What did people say about test?", messages)
    
    print(f"Response: {response.content}")
    print(f"Time: {response.response_time:.2f}s")
    print(f"Success: {response.success}")
```

**Day 3-4: Performance Benchmarking**
```python
# Implement benchmarking suite
async def benchmark_llm_performance():
    handler = DiscordLLMHandler()
    
    # Test different context lengths
    context_sizes = [1000, 2000, 4000, 6000]
    
    for size in context_sizes:
        handler.max_context_length = size
        
        start_time = time.time()
        response = await handler.generate_response_async(
            "Summarize the discussion", 
            get_sample_messages(size)
        )
        end_time = time.time()
        
        print(f"Context size {size}: {end_time - start_time:.2f}s")
        print(f"Success: {response.success}")
        print(f"Tokens: {response.tokens_used}")
        print("---")

# Document results in your sprint notes
```

**Day 5: Integration with FastAPI**
```python
# Add LLM endpoint to your existing FastAPI app
@app.post("/api/llm/query")
async def llm_query(request: LLMQueryRequest):
    try:
        # Get messages from ChromaDB
        search_results = await chromadb_service.search(
            request.query, 
            limit=request.max_results or 10
        )
        
        # Convert to MessageContext
        messages = [
            MessageContext(
                content=result.document,
                author=result.metadata['author'],
                channel=result.metadata['channel'],
                timestamp=datetime.fromisoformat(result.metadata['timestamp']),
                message_id=result.metadata['message_id'],
                similarity_score=result.distance
            )
            for result in search_results
        ]
        
        # Generate response
        response = await llm_handler.generate_response_async(
            request.query, 
            messages
        )
        
        return {
            "response": response.content,
            "success": response.success,
            "metadata": {
                "response_time": response.response_time,
                "tokens_used": response.tokens_used,
                "messages_retrieved": len(messages)
            }
        }
        
    except Exception as e:
        logging.error(f"LLM query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### Week 6 Tasks

**Day 1-2: Error Handling and Resilience**
```python
# Implement comprehensive error handling
class ProductionLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.circuit_breaker = CircuitBreaker()
        self.retry_count = 3
        
    async def generate_response_with_retry(self, query: str, messages: List[MessageContext]) -> LLMResponse:
        last_error = None
        
        for attempt in range(self.retry_count):
            try:
                if self.circuit_breaker.is_open():
                    break
                    
                response = await self.generate_response_async(query, messages)
                
                if response.success:
                    self.circuit_breaker.record_success()
                    return response
                else:
                    self.circuit_breaker.record_failure()
                    last_error = response.error
                    
            except Exception as e:
                self.circuit_breaker.record_failure()
                last_error = str(e)
                logging.warning(f"LLM attempt {attempt + 1} failed: {e}")
                
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # All retries failed, return error response
        return LLMResponse(
            content="I'm having trouble processing your request right now. Please try again later.",
            tokens_used=0,
            response_time=0,
            model_used=self.model_name,
            success=False,
            error=f"All retries failed. Last error: {last_error}"
        )

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def is_open(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                return False
            return True
        return False
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

**Day 3-4: Caching Implementation**
```python
# Add Redis-based caching for production
import redis
import pickle

class CachedLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.cache_ttl = 3600  # 1 hour
    
    def _generate_cache_key(self, query: str, messages: List[MessageContext]) -> str:
        # Create deterministic cache key
        content_hash = hashlib.sha256()
        content_hash.update(query.encode())
        
        for msg in messages:
            content_hash.update(f"{msg.content}{msg.author}{msg.timestamp}".encode())
        
        return f"llm_response:{content_hash.hexdigest()}"
    
    async def generate_response_async(self, query: str, retrieved_messages: List[MessageContext]) -> LLMResponse:
        cache_key = self._generate_cache_key(query, retrieved_messages)
        
        # Try cache first
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                cached_response = pickle.loads(cached_data)
                logging.info("Returning cached LLM response")
                return cached_response
        except Exception as e:
            logging.warning(f"Cache retrieval error: {e}")
        
        # Generate new response
        response = await super().generate_response_async(query, retrieved_messages)
        
        # Cache successful responses
        if response.success:
            try:
                self.redis_client.setex(
                    cache_key, 
                    self.cache_ttl, 
                    pickle.dumps(response)
                )
            except Exception as e:
                logging.warning(f"Cache storage error: {e}")
        
        return response
```

**Day 5: Testing and Documentation**
```python
# Comprehensive test suite
@pytest.mark.asyncio
async def test_production_ready_features():
    handler = ProductionLLMHandler()
    
    # Test circuit breaker
    for i in range(10):
        response = await handler.generate_response_with_retry(
            "test query", 
            []
        )
        
        if not response.success and "circuit breaker" in response.error:
            print("✅ Circuit breaker working")
            break
    
    # Test caching
    cached_handler = CachedLLMHandler()
    
    messages = get_sample_messages()
    
    # First call
    start = time.time()
    response1 = await cached_handler.generate_response_async("test", messages)
    time1 = time.time() - start
    
    # Second call (should be cached)
    start = time.time()
    response2 = await cached_handler.generate_response_async("test", messages)
    time2 = time.time() - start
    
    assert time2 < time1 / 2  # Should be much faster
    assert response1.content == response2.content
    print("✅ Caching working")
```

### Sprint 4: Discord Bot User Interface (Weeks 7-8)

#### Integration with Discord Bot

```python
# Enhanced Discord bot with LLM integration
import discord
from discord.ext import commands

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        
        super().__init__(command_prefix='!', intents=intents)
        
        # Initialize components
        self.llm_handler = ProductionLLMHandler()
        self.chromadb = ChromaDBService()
        
        # Bot state
        self.indexing_active = False
        self.user_sessions = {}
    
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print(f'LLM Health: {self.llm_handler.health_check()}')
    
    async def on_message(self, message):
        # Handle DMs
        if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
            await self.handle_dm_query(message)
        
        # Handle mentions in servers
        elif self.user.mentioned_in(message) and not message.author.bot:
            await self.handle_mention_query(message)
        
        await self.process_commands(message)
    
    async def handle_dm_query(self, message):
        """Handle direct message queries"""
        user_id = message.author.id
        query = message.content.strip()
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Search ChromaDB
                search_results = await self.chromadb.search(query, limit=8)
                
                if not search_results:
                    await message.channel.send(
                        "I couldn't find any relevant messages in the server history for that query. "
                        "Try rephrasing your question or asking about something more specific!"
                    )
                    return
                
                # Convert to MessageContext
                messages = self._convert_search_results(search_results)
                
                # Generate response
                response = await self.llm_handler.generate_response_with_retry(query, messages)
                
                if response.success:
                    # Format response for Discord
                    formatted_response = self._format_discord_response(
                        response.content, 
                        len(messages),
                        response.response_time
                    )
                    
                    await message.channel.send(formatted_response)
                    
                    # Log metrics
                    logging.info(f"User {user_id} query processed: {response.response_time:.2f}s, "
                               f"{response.tokens_used} tokens, {len(messages)} messages")
                else:
                    await message.channel.send(
                        "I'm having trouble processing your request right now. "
                        "Please try again in a few moments! 🤖"
                    )
                    
            except Exception as e:
                logging.error(f"Error handling DM query: {e}")
                await message.channel.send(
                    "Something went wrong while processing your request. "
                    "Please try again or contact an admin if the problem persists."
                )
    
    def _convert_search_results(self, search_results) -> List[MessageContext]:
        """Convert ChromaDB results to MessageContext objects"""
        messages = []
        
        for result in search_results:
            try:
                messages.append(MessageContext(
                    content=result.document,
                    author=result.metadata.get('author', 'Unknown'),
                    channel=result.metadata.get('channel', 'unknown'),
                    timestamp=datetime.fromisoformat(
                        result.metadata.get('timestamp', datetime.now().isoformat())
                    ),
                    message_id=result.metadata.get('message_id', ''),
                    similarity_score=1 - result.distance  # Convert distance to similarity
                ))
            except Exception as e:
                logging.warning(f"Error converting search result: {e}")
                continue
        
        return messages
    
    def _format_discord_response(self, content: str, num_messages: int, response_time: float) -> str:
        """Format LLM response for Discord"""
        
        # Add footer with metadata
        footer = f"\n\n*Based on {num_messages} messages • Response time: {response_time:.1f}s*"
        
        # Ensure we don't exceed Discord's limit
        max_content_length = 1950 - len(footer)
        
        if len(content) > max_content_length:
            content = content[:max_content_length-50] + "\n\n*[Response truncated]*"
        
        return content + footer
    
    @commands.command(name='query')
    async def query_command(self, ctx, *, question: str):
        """Manual query command for servers"""
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("You can just send me messages directly! No need for commands in DMs.")
            return
        
        # Handle the query similar to DM handling
        await self.handle_dm_query(ctx.message)
    
    @commands.command(name='status')
    async def status_command(self, ctx):
        """Show bot status and metrics"""
        embed = discord.Embed(title="Bot Status", color=0x00ff00)
        
        # LLM health
        llm_healthy = self.llm_handler.health_check()
        embed.add_field(
            name="🤖 LLM Status", 
            value="✅ Online" if llm_healthy else "❌ Offline", 
            inline=True
        )
        
        # Database status
        try:
            db_count = await self.chromadb.get_message_count()
            embed.add_field(
                name="📚 Indexed Messages", 
                value=f"{db_count:,}", 
                inline=True
            )
        except:
            embed.add_field(name="📚 Database", value="❌ Error", inline=True)
        
        # Performance metrics
        if hasattr(self.llm_handler, 'get_metrics'):
            metrics = self.llm_handler.get_metrics()
            embed.add_field(
                name="📊 Performance",
                value=f"Avg Response: {metrics.get('average_response_time', 0):.2f}s\n"
                      f"Success Rate: {metrics.get('success_rate', 0)*100:.1f}%",
                inline=True
            )
        
        # Indexing status
        embed.add_field(
            name="🔄 Indexing", 
            value="✅ Active" if self.indexing_active else "⏸️ Paused", 
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='help_bot')
    async def help_command(self, ctx):
        """Show bot help information"""
        embed = discord.Embed(
            title="Discord Indexer Bot Help", 
            description="I help you search through server message history!",
            color=0x0099ff
        )
        
        embed.add_field(
            name="💬 Direct Messages",
            value="Send me a DM with any question about the server's history. "
                  "I'll search through past messages and provide relevant information!",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Example Queries",
            value="• 'What did people say about the new update?'\n"
                  "• 'When was the last server event?'\n"
                  "• 'Who mentioned Python recently?'\n"
                  "• 'Summarize yesterday's discussion'",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Commands",
            value="`!status` - Check bot status\n"
                  "`!query <question>` - Ask a question in this channel\n"
                  "`!help_bot` - Show this help message",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Be specific in your questions\n"
                  "• I work best with questions about recent activity\n"
                  "• If I can't find something, try rephrasing your question",
            inline=False
        )
        
        await ctx.send(embed=embed)

# Bot initialization
if __name__ == "__main__":
    bot = DiscordBot()
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
```

### Sprint 5: Performance & Reliability (Week 9)

#### Monitoring and Metrics

```python
# Advanced monitoring system
class LLMMetricsCollector:
    def __init__(self):
        self.metrics = {
            'requests_total': 0,
            'requests_successful': 0,
            'avg_response_time': 0,
            'avg_tokens_per_request': 0,
            'peak_response_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'error_types': defaultdict(int),
            'hourly_stats': defaultdict(lambda: {'requests': 0, 'avg_time': 0})
        }
        self.start_time = time.time()
    
    def record_request(self, response: LLMResponse, cached: bool = False):
        self.metrics['requests_total'] += 1
        
        if response.success:
            self.metrics['requests_successful'] += 1
            
            # Update running averages
            n = self.metrics['requests_successful']
            prev_avg_time = self.metrics['avg_response_time']
            self.metrics['avg_response_time'] = (
                (prev_avg_time * (n-1) + response.response_time) / n
            )
            
            prev_avg_tokens = self.metrics['avg_tokens_per_request']
            self.metrics['avg_tokens_per_request'] = (
                (prev_avg_tokens * (n-1) + response.tokens_used) / n
            )
            
            # Track peak response time
            if response.response_time > self.metrics['peak_response_time']:
                self.metrics['peak_response_time'] = response.response_time
        else:
            self.metrics['error_types'][response.error] += 1
        
        # Cache metrics
        if cached:
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
        
        # Hourly stats
        hour = datetime.now().hour
        hourly = self.metrics['hourly_stats'][hour]
        hourly['requests'] += 1
        prev_avg = hourly['avg_time']
        hourly['avg_time'] = (
            (prev_avg * (hourly['requests']-1) + response.response_time) / hourly['requests']
        )
    
    def get_summary(self) -> dict:
        uptime = time.time() - self.start_time
        success_rate = (
            self.metrics['requests_successful'] / max(1, self.metrics['requests_total'])
        )
        cache_hit_rate = (
            self.metrics['cache_hits'] / 
            max(1, self.metrics['cache_hits'] + self.metrics['cache_misses'])
        )
        
        return {
            'uptime_seconds': uptime,
            'success_rate': success_rate,
            'cache_hit_rate': cache_hit_rate,
            'requests_per_minute': self.metrics['requests_total'] / max(1, uptime / 60),
            **self.metrics
        }
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        summary = self.get_summary()
        
        metrics = [
            f"llm_requests_total {summary['requests_total']}",
            f"llm_requests_successful {summary['requests_successful']}",
            f"llm_avg_response_time_seconds {summary['avg_response_time']}",
            f"llm_peak_response_time_seconds {summary['peak_response_time']}",
            f"llm_success_rate {summary['success_rate']}",
            f"llm_cache_hit_rate {summary['cache_hit_rate']}",
            f"llm_uptime_seconds {summary['uptime_seconds']}"
        ]
        
        return '\n'.join(metrics)

# Integration with FastAPI for metrics endpoint
@app.get("/metrics")
async def get_metrics():
    return llm_metrics_collector.get_summary()

@app.get("/metrics/prometheus")
async def get_prometheus_metrics():
    return Response(
        content=llm_metrics_collector.export_prometheus_metrics(),
        media_type="text/plain"
    )
```

#### Health Check and Auto-Recovery

```python
class HealthCheckManager:
    def __init__(self, llm_handler: DiscordLLMHandler):
        self.llm_handler = llm_handler
        self.last_health_check = time.time()
        self.health_check_interval = 300  # 5 minutes
        self.consecutive_failures = 0
        self.max_failures = 3
        
    async def periodic_health_check(self):
        """Run periodic health checks in background"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self.check_health()
            except Exception as e:
                logging.error(f"Health check error: {e}")
    
    async def check_health(self) -> bool:
        """Perform health check and recovery if needed"""
        try:
            is_healthy = self.llm_handler.health_check()
            
            if is_healthy:
                if self.consecutive_failures > 0:
                    logging.info("LLM recovered after health check failure")
                self.consecutive_failures = 0
                return True
            else:
                self.consecutive_failures += 1
                logging.warning(f"Health check failed ({self.consecutive_failures}/{self.max_failures})")
                
                if self.consecutive_failures >= self.max_failures:
                    await self.attempt_recovery()
                
                return False
                
        except Exception as e:
            logging.error(f"Health check exception: {e}")
            self.consecutive_failures += 1
            return False
    
    async def attempt_recovery(self):
        """Attempt to recover LLM service"""
        logging.info("Attempting LLM recovery...")
        
        try:
            # Try restarting Ollama service
            import subprocess
            result = subprocess.run(['systemctl', 'restart', 'ollama'], capture_output=True)
            
            if result.returncode == 0:
                # Wait for service to start
                await asyncio.sleep(10)
                
                # Test health again
                if self.llm_handler.health_check():
                    logging.info("LLM recovery successful")
                    self.consecutive_failures = 0
                    return True
            
            logging.error("LLM recovery failed")
            return False
            
        except Exception as e:
            logging.error(f"Recovery attempt failed: {e}")
            return False

# Integration with Discord bot
class RobustDiscordBot(DiscordBot):
    def __init__(self):
        super().__init__()
        self.health_manager = HealthCheckManager(self.llm_handler)
        self.metrics_collector = LLMMetricsCollector()
        
    async def on_ready(self):
        await super().on_ready()
        
        # Start background health checks
        self.loop.create_task(self.health_manager.periodic_health_check())
    
    async def handle_dm_query(self, message):
        """Enhanced DM handler with metrics and health checks"""
        
        # Check health before processing
        if not await self.health_manager.check_health():
            await message.channel.send(
                "I'm currently experiencing technical difficulties. "
                "Please try again in a few minutes! 🔧"
            )
            return
        
        # Process query with metrics collection
        start_time = time.time()
        cached = False
        
        try:
            # Your existing query processing logic here...
            response = await self.llm_handler.generate_response_with_retry(query, messages)
            
            # Record metrics
            self.metrics_collector.record_request(response, cached)
            
            # Send response
            if response.success:
                await message.channel.send(response.content)
            else:
                await message.channel.send("Sorry, I couldn't process that request.")
                
        except Exception as e:
            logging.error(f"Error in enhanced DM handler: {e}")
            
            # Create error response for metrics
            error_response = LLMResponse(
                content="",
                tokens_used=0,
                response_time=time.time() - start_time,
                model_used=self.llm_handler.model_name,
                success=False,
                error=str(e)
            )
            self.metrics_collector.record_request(error_response)
            
            await message.channel.send("Something went wrong. Please try again!")
```

### Future Enhancements (Post-Sprint)

#### Advanced Features Implementation

```python
# Multi-server support
class MultiServerLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_contexts = {}  # Cache server-specific context
    
    def get_server_context(self, guild_id: int) -> str:
        """Get server-specific system context"""
        if guild_id not in self.server_contexts:
            # Load server-specific information
            self.server_contexts[guild_id] = self.load_server_context(guild_id)
        
        return self.server_contexts[guild_id]
    
    def create_server_system_prompt(self, guild_id: int) -> str:
        base_prompt = self.create_system_prompt()
        server_context = self.get_server_context(guild_id)
        
        return f"{base_prompt}\n\nServer-specific context:\n{server_context}"

# User preference system
class PersonalizedLLMHandler(DiscordLLMHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_preferences = {}
    
    def get_user_preferences(self, user_id: int) -> dict:
        return self.user_preferences.get(user_id, {
            'response_length': 'medium',
            'formality': 'casual',
            'include_timestamps': True,
            'max_context_messages': 8
        })
    
    def customize_response_for_user(self, user_id: int, response: str) -> str:
        prefs = self.get_user_preferences(user_id)
        
        # Adjust response based on preferences
        if prefs['response_length'] == 'short':
            # Truncate to essential information
            response = self.truncate_response(response, 500)
        elif prefs['response_length'] == 'long':
            # Allow longer responses
            pass
        
        if prefs['formality'] == 'formal':
            # Adjust tone (would need more sophisticated processing)
            pass
        
        return response
```

---

## Conclusion

This documentation provides a comprehensive guide for implementing LLM integration in your Discord Bot Indexing Project. The `DiscordLLMHandler` class is designed to be:

- **Production-ready** with comprehensive error handling and monitoring
- **Discord-optimized** for character limits and user experience  
- **Performance-focused** with caching and async support
- **Maintainable** with clear interfaces and extensive logging
- **Scalable** with circuit breakers and health checks

### Key Takeaways for the Development Team

1. **Start Simple**: Begin with the basic `DiscordLLMHandler` class and add features incrementally
2. **Monitor Everything**: Use the metrics collection system to understand performance
3. **Handle Failures Gracefully**: Implement proper error handling and fallbacks
4. **Test Thoroughly**: Use the provided test suites to ensure reliability
5. **Optimize for Discord**: Remember the 2000 character limit and user experience

### Next Steps

1. **Sprint 3 Week 1**: Implement basic integration and run initial tests
2. **Sprint 3 Week 2**: Add error handling and caching
3. **Sprint 4**: Integrate with Discord bot DM interface
4. **Sprint 5**: Add monitoring and production hardening
5. **Future**: Consider advanced features like multi-server support

The system is designed to meet your performance targets (<5 second response times) while running efficiently on 8GB VRAM hardware. Follow the sprint integration guide for systematic implementation and testing.