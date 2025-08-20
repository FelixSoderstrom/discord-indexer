# Discord Rate Limiter Implementation Guide

## 🎯 Overview

The `DiscordRateLimiter` class provides intelligent rate limiting for Discord API calls while enabling unlimited parallel processing of fetched data. This approach separates concerns: **rate-limited fetching** from Discord and **unlimited parallel processing** of the data.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DiscordRateLimiter                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Request Queue   │  │ Rate Monitoring │  │ Retry Logic │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DiscordBot                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Message Fetch   │  │ Message Process │  │ Message     │ │
│  │ (Rate Limited)  │  │ (Unlimited)     │  │ Storage     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Core Features

- **Automatic Rate Limiting**: Respects Discord's 50 requests/second limit
- **Parallel Processing**: Unlimited concurrent processing of fetched data
- **Retry Logic**: Automatic retry with exponential backoff
- **Monitoring**: Real-time status and performance metrics
- **Configurable**: Adjustable limits and concurrency levels

## 📁 File Structure

```
src/
├── bot/
│   ├── rate_limiter.py          # Main rate limiter class
│   ├── client.py                # DiscordBot using rate limiter
│   └── actions.py               # Event handlers
└── config/
    └── settings.py              # Rate limit configuration
```

## 🚀 Basic Usage

### 1. Initialize the Rate Limiter

```python
from src.bot.rate_limiter import DiscordRateLimiter

# Basic initialization
rate_limiter = DiscordRateLimiter()

# Custom configuration
rate_limiter = DiscordRateLimiter(
    max_requests_per_second=50,    # Discord's limit
    burst_limit=100,               # Maximum burst requests
    retry_delay=1.0,              # Base retry delay
    max_retries=3                  # Maximum retry attempts
)
```

### 2. Basic Rate-Limited API Call

```python
async def fetch_user_info(user_id: int):
    async def api_call():
        # Your Discord API call here
        return await bot.fetch_user(user_id)
    
    # Execute with automatic rate limiting
    result = await rate_limiter.execute_with_rate_limit(api_call)
    return result
```

### 3. Check Rate Limiter Status

```python
# Get current status
status = rate_limiter.get_status()
print(f"Current requests: {status['current_requests']}")
print(f"Queue size: {status['request_queue_size']}")

# Reset if needed
await rate_limiter.reset()
```

## 🔄 Parallel Processing Examples

### Example 1: Parallel Message Fetching

The rate limiter's `batch_fetch_messages` method demonstrates the recommended approach:

```python
async def fetch_all_messages_parallel():
    channels = bot.get_all_channels()
    
    # Fetch from all channels with rate limiting and parallel processing
    all_messages = await rate_limiter.batch_fetch_messages(
        channels=channels,
        messages_per_channel=1000,
        max_concurrent_channels=5  # Adjust based on your needs
    )
    
    return all_messages
```

**What happens internally:**
1. **Rate-limited fetching**: Respects Discord's 50 req/sec limit
2. **Parallel processing**: Multiple channels processed simultaneously
3. **Controlled concurrency**: Limits concurrent channel fetching
4. **Error handling**: Gracefully handles failed channel fetches

### Example 2: Parallel Message Processing (After Fetching)

```python
async def process_messages_parallel(messages: List[Dict[str, Any]]):
    """Process messages in parallel after they're fetched."""
    
    async def process_single_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single message (embeddings, vision, etc.)."""
        processed = message.copy()
        
        # Generate embeddings (CPU-intensive, can be parallel)
        if message['content']:
            processed['embedding'] = await generate_embedding(message['content'])
        
        # Process images (can be parallel)
        if message['attachments']:
            processed['vision_data'] = await process_images_parallel(message['attachments'])
        
        return processed
    
    # Process all messages in parallel
    tasks = [process_single_message(msg) for msg in messages]
    processed_messages = await asyncio.gather(*tasks, return_exceptions=True)
    
    return processed_messages
```

### Example 3: Vision Processing in Parallel

```python
async def process_images_parallel(image_urls: List[str]) -> List[Dict[str, Any]]:
    """Process multiple images in parallel."""
    
    async def process_single_image(url: str) -> Dict[str, Any]:
        """Process a single image."""
        # This is where you'd call your vision model
        # No rate limiting needed for local processing
        return {
            'url': url,
            'description': 'Image description from vision model',
            'tags': ['tag1', 'tag2'],
            'processed_at': time.time()
        }
    
    # Process all images simultaneously
    tasks = [process_single_image(url) for url in image_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return [r for r in results if not isinstance(r, Exception)]
```

## 🔌 Integration with DiscordBot

### Step 1: Update DiscordBot Class

```python:src/bot/client.py
from .rate_limiter import DiscordRateLimiter

class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=settings.COMMAND_PREFIX,
            intents=settings.get_intents,
            help_command=None
        )
        # Add rate limiter
        self.rate_limiter = DiscordRateLimiter()
        self.stored_messages = []
        self.processed_channels = []
        self.logger = logging.getLogger(__name__)
    
    async def get_all_historical_messages(self) -> List[Dict[str, Any]]:
        """Fetch all historical messages with rate limiting and parallel processing."""
        channels = self.get_all_channels()
        
        self.logger.info(f"Processing {len(channels)} channels with rate limiting...")
        
        # Use the rate limiter for parallel processing
        all_messages = await self.rate_limiter.batch_fetch_messages(
            channels=channels,
            messages_per_channel=1000,
            max_concurrent_channels=5
        )
        
        self.logger.info(f"Total messages fetched: {len(all_messages)}")
        self.stored_messages.extend(all_messages)
        return all_messages
```

### Step 2: Update Actions

```python:src/bot/actions.py
async def on_ready_handler(bot: "DiscordBot") -> None:
    """Handle bot ready event with rate limiting."""
    logger = logging.getLogger(__name__)
    logger.info("=== Bot is ready! Now monitoring for new messages... ===")
    
    # Log rate limiter status
    status = bot.rate_limiter.get_status()
    logger.info(f"Rate limiter status: {status}")
    
    # Log available channels
    channels = bot.get_all_channels()
    logger.info(f"📡 Monitoring {len(channels)} channels for new messages")
```

## ⚙️ Configuration

### Rate Limiter Settings

Add these to your `settings.py`:

```python:src/config/settings.py
# Discord Rate Limiting Configuration
DISCORD_RATE_LIMIT_MAX_PER_SECOND = 50
DISCORD_RATE_LIMIT_BURST_LIMIT = 100
DISCORD_RATE_LIMIT_RETRY_DELAY = 1.0
DISCORD_RATE_LIMIT_MAX_RETRIES = 3
DISCORD_MAX_CONCURRENT_CHANNELS = 5
```

### Usage in Bot

```python
# Initialize with custom settings
self.rate_limiter = DiscordRateLimiter(
    max_requests_per_second=settings.DISCORD_RATE_LIMIT_MAX_PER_SECOND,
    burst_limit=settings.DISCORD_RATE_LIMIT_BURST_LIMIT,
    retry_delay=settings.DISCORD_RATE_LIMIT_RETRY_DELAY,
    max_retries=settings.DISCORD_RATE_LIMIT_MAX_RETRIES
)
```

## 📊 Monitoring and Debugging

### Logging Configuration

```python
# Add this to your logging setup for detailed rate limiting info
logging.getLogger('src.bot.rate_limiter').setLevel(logging.DEBUG)
```

### Status Monitoring

```python
# Get current status
status = bot.rate_limiter.get_status()
print(f"Current requests: {status['current_requests']}")
print(f"Queue size: {status['request_queue_size']}")
print(f"Last reset: {status['last_reset']}")

# Reset if needed
await bot.rate_limiter.reset()
```

### Performance Metrics

```python
async def monitor_performance():
    """Monitor rate limiter performance."""
    while True:
        status = bot.rate_limiter.get_status()
        
        # Log performance metrics
        logger.info(f"Rate limiter performance: {status}")
        
        # Check for potential issues
        if status['current_requests'] > status['max_requests_per_second'] * 0.8:
            logger.warning("Rate limiter approaching capacity")
        
        await asyncio.sleep(60)  # Check every minute
```

## 🎯 Best Practices

### 1. **Separate Fetching from Processing**
- Use rate limiting only for Discord API calls
- Process fetched data without any limits
- This maximizes throughput while respecting Discord's limits

### 2. **Adjust Concurrency Levels**
```python
# For high-traffic servers
max_concurrent_channels = 3  # Conservative

# For low-traffic servers
max_concurrent_channels = 10  # Aggressive

# Monitor and adjust based on performance
```

### 3. **Handle Errors Gracefully**
```python
try:
    messages = await rate_limiter.batch_fetch_messages(channels)
except Exception as e:
    logger.error(f"Batch fetch failed: {e}")
    # Fallback to sequential processing
    messages = await fallback_sequential_fetch(channels)
```

### 4. **Monitor Memory Usage**
```python
import psutil

async def check_memory_usage():
    """Monitor memory usage during parallel processing."""
    process = psutil.Process()
    memory_info = process.memory_info()
    
    if memory_info.rss > 1_000_000_000:  # 1GB
        logger.warning("High memory usage detected")
        # Consider reducing batch size or concurrency
```

## 🚨 Common Pitfalls

### 1. **Too Many Concurrent Channels**
```python
# ❌ Bad: Too many concurrent channels
max_concurrent_channels = 50  # May overwhelm Discord

# ✅ Good: Reasonable concurrency
max_concurrent_channels = 5   # Balanced approach
```

### 2. **Ignoring Rate Limit Headers**
```python
# ❌ Bad: Hard-coded delays
await asyncio.sleep(0.02)  # May not respect actual limits

# ✅ Good: Use rate limiter
await rate_limiter.execute_with_rate_limit(api_call)
```

### 3. **No Error Handling**
```python
# ❌ Bad: No error handling
messages = await rate_limiter.batch_fetch_messages(channels)

# ✅ Good: Proper error handling
try:
    messages = await rate_limiter.batch_fetch_messages(channels)
except Exception as e:
    logger.error(f"Failed to fetch messages: {e}")
    messages = []
```

## 🔄 Advanced Usage Patterns

### 1. **Custom Rate Limiting Strategies**

```python
class CustomRateLimiter(DiscordRateLimiter):
    async def adaptive_rate_limit(self):
        """Adapt rate limiting based on Discord's response headers."""
        # Implement custom logic here
        pass
```

### 2. **Distributed Rate Limiting**

```python
class DistributedRateLimiter(DiscordRateLimiter):
    def __init__(self, redis_client):
        super().__init__()
        self.redis = redis_client
    
    async def acquire(self):
        """Use Redis for distributed rate limiting."""
        # Implement distributed logic
        pass
```

### 3. **Priority Queuing**

```python
class PriorityRateLimiter(DiscordRateLimiter):
    async def execute_with_priority(self, api_call, priority: int = 0):
        """Execute API calls with priority-based queuing."""
        # Implement priority logic
        pass
```

## 📈 Performance Tuning

### 1. **Benchmark Different Configurations**

```python
async def benchmark_configurations():
    """Test different rate limiter configurations."""
    configs = [
        {'max_concurrent_channels': 3},
        {'max_concurrent_channels': 5},
        {'max_concurrent_channels': 10}
    ]
    
    for config in configs:
        start_time = time.time()
        rate_limiter = DiscordRateLimiter(**config)
        
        # Test with sample channels
        messages = await rate_limiter.batch_fetch_messages(test_channels)
        
        duration = time.time() - start_time
        print(f"Config {config}: {len(messages)} messages in {duration:.2f}s")
```

### 2. **Memory Optimization**

```python
async def process_in_batches(messages: List[Dict], batch_size: int = 1000):
    """Process messages in batches to manage memory."""
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        
        # Process batch in parallel
        processed_batch = await process_messages_parallel(batch)
        
        # Store or yield results
        yield processed_batch
        
        # Optional: Small delay between batches
        await asyncio.sleep(0.1)
```

## 🔍 Troubleshooting

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Rate limit errors | Too many concurrent requests | Reduce `max_concurrent_channels` |
| Memory issues | Large message batches | Process in smaller batches |
| Slow performance | Too few concurrent channels | Increase `max_concurrent_channels` |
| Connection timeouts | Network issues | Increase `retry_delay` and `max_retries` |

### Debug Mode

```python
# Enable debug logging
logging.getLogger('src.bot.rate_limiter').setLevel(logging.DEBUG)

# This will show detailed rate limiting information:
# - When requests are queued
# - When rate limits are hit
# - Retry attempts and delays
# - Semaphore acquisition/release
```

## 📚 Next Steps

1. **Integrate the rate limiter** into your existing bot
2. **Test with a small number of channels** first
3. **Monitor performance** and adjust concurrency levels
4. **Add parallel processing** for embeddings and vision
5. **Scale up gradually** while monitoring resource usage

## 🎉 Summary

The `DiscordRateLimiter` provides a robust, scalable solution for:
- **Respecting Discord's rate limits** automatically
- **Maximizing processing throughput** with parallel execution
- **Handling errors gracefully** with retry logic
- **Monitoring performance** in real-time
- **Scaling efficiently** as your needs grow

This architecture separates concerns effectively and provides a solid foundation for building high-performance Discord applications.
