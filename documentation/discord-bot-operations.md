# Discord Bot Operations & Client Management

## Overview

The Discord Indexer Bot is a sophisticated message processing and AI-powered search system built on Discord.py 2.6.0. The bot architecture focuses on real-time message indexing, intelligent conversation handling, stateless queue-based processing, and dual-model AI capabilities (text and vision) with local LLM processing through Ollama.

## Architecture Overview

### Core Components

The bot system consists of six primary components that work together:

1. **DiscordBot Client** (`src/bot/client.py`) - Main bot connection and lifecycle management
2. **Event Handlers** (`src/bot/actions.py`) - Message routing and command processing
3. **Rate Limiter** (`src/bot/rate_limiter.py`) - Discord API compliance and optimization
4. **Message Processing** (`src/message_processing/`) - Async message processing pipeline
5. **Model Management** (`src/ai/model_manager.py`) - Dual model system for text and vision processing
6. **Queue System** - Fair queue-based conversation handling with LangChain integration

```python
# Key architectural relationship
class DiscordBot(commands.Bot):
    def __init__(self):
        # Pipeline coordination
        self.pipeline_ready = asyncio.Event()
        self.message_pipeline: Optional["MessagePipeline"] = None
        self.batch_size = 1000
        
        # DMAssistant for conversations (LangChain-based)
        self.dm_assistant: Optional["DMAssistant"] = None
        self.queue_worker = None
        
        # Rate limiting and processing
        self.rate_limiter = DiscordRateLimiter()
        
        # Legacy storage (transitioning to pipeline)
        self.stored_messages: List[Dict[str, Any]] = []
        self.processed_channels: List[int] = []
```

### Design Principles

- **Separation of Concerns**: Bot handles Discord operations; pipeline handles processing
- **Stateless Processing**: No persistent sessions; queue-based conversation handling
- **Dual Model Architecture**: Separate text and vision models for comprehensive processing
- **Smart Resumption**: Checkpoint-based processing to avoid reprocessing existing messages
- **Backpressure Management**: Pipeline coordination prevents memory overflow
- **Rate Limit Compliance**: Automatic Discord API rate limiting with retry logic
- **Local-First AI**: All LLM processing through local Ollama instance (no external APIs)

## Connection & Lifecycle Management

### Bot Startup Sequence

The bot follows a strict initialization sequence to ensure all components are ready:

```python
async def on_ready_handler(bot: "DiscordBot") -> None:
    # 1. Configure all servers before processing
    setup_success = configure_all_servers(bot.guilds)
    if not setup_success:
        logger.error("Server configuration failed - some servers may not be processed")
    
    # 2. Initialize message processing pipeline
    bot.message_pipeline = MessagePipeline(completion_event=bot.pipeline_ready)
    
    # 3. Initialize LangChain DMAssistant with async health check
    bot.dm_assistant = LangChainDMAssistant()
    health_check_passed = await bot.dm_assistant.health_check_async(timeout_seconds=120.0)
    if not health_check_passed:
        raise RuntimeError("LangChain DMAssistant model not available or not responsive")
    
    # 4. Start queue worker for conversation processing
    queue_worker = initialize_queue_worker(use_langchain=True)
    await queue_worker.start()
    bot.queue_worker = queue_worker
    
    # 5. Process historical messages using smart resumption
    historical_success = await bot.resume_indexing_from_checkpoints()
    
    # 6. Begin real-time monitoring
    if historical_success:
        logger.info("Now monitoring for new real-time messages...")
```

### Graceful Shutdown

The bot implements comprehensive cleanup to prevent resource leaks:

```python
async def close(self) -> None:
    # Clear message pipeline reference
    if self.message_pipeline:
        self.message_pipeline = None
    
    # Stop queue worker
    if self.queue_worker:
        await self.queue_worker.stop()
        self.queue_worker = None
    
    # Clear DMAssistant reference
    if self.dm_assistant:
        self.dm_assistant = None
    
    await super().close()
```

### Error Handling & Recovery

Critical failures trigger immediate shutdown to prevent inconsistent states:

```python
# Pipeline failure handling
if not success:
    logger.critical("Pipeline failure - shutting down")
    await bot.close()
    sys.exit(1)
```

## Event Handling System

### Message Routing Architecture

The event system implements intelligent message routing based on message type and context:

```python
async def on_message_handler(bot: "DiscordBot", message: discord.Message) -> None:
    # Skip bot's own messages
    if message.author == bot.user:
        return
    
    # Route DM messages
    if isinstance(message.channel, discord.DMChannel):
        if message.content.startswith(bot.command_prefix):
            return  # Let commands extension handle
        else:
            await handle_dm_message(bot, message)  # Provide guidance
        return
    
    # Route server messages to async processing pipeline
    if message.guild and not message.content.startswith(bot.command_prefix):
        # Check if server is configured
        if not is_server_configured(str(message.guild.id)):
            logger.warning(f"Skipping message indexing for unconfigured server")
            return
        
        # Convert to processing format and use async pipeline
        message_data = {
            'id': message.id,
            'content': message.content,
            'author_id': message.author.id,
            'author_name': message.author.display_name,
            'channel_id': message.channel.id,
            'guild_id': message.guild.id,
            'timestamp': message.created_at.isoformat(),
            'attachments': [{
                'url': att.url,
                'filename': att.filename,
                'content_type': att.content_type
            } for att in message.attachments]
        }
        await process_message_async(message_data)
```

### Real-time Message Processing

Server messages are immediately processed through the pipeline with backpressure control:

```python
async def send_batch_to_pipeline(self, messages: List[Dict[str, Any]]) -> bool:
    # Clear ready event before processing
    self.pipeline_ready.clear()
    
    # Send to pipeline
    success = await self.message_pipeline.process_messages(messages)
    
    # Wait for pipeline completion
    await self.pipeline_ready.wait()
    
    return success
```

### Command Processing

Commands use Discord.py's commands extension with proper error handling:

```python
@bot.command(name='ask')
async def ask_command(ctx: commands.Context, *, message: str = None):
    # DM-only enforcement for privacy
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("DM Only: Commands only work in direct messages")
        return
    
    # Queue-based processing with fair scheduling
    queue = get_conversation_queue()
    success = await queue.add_request(
        user_id=str(ctx.author.id),
        server_id=selected_server.server_id,
        message=message,
        discord_message_id=ctx.message.id,
        discord_channel=ctx.channel
    )
```

## Rate Limiting Strategy

### Discord API Compliance

The rate limiter implements Discord's 50 requests/second limit with burst handling:

```python
class DiscordRateLimiter:
    def __init__(self, max_requests_per_second: int = 50, burst_limit: int = 100):
        self.request_times = deque(maxlen=burst_limit)
        self.request_semaphore = asyncio.Semaphore(max_requests_per_second)
```

### Parallel Processing Strategy

The system separates rate-limited fetching from unlimited processing:

```python
async def batch_fetch_messages(
    self,
    channels: List[discord.TextChannel],
    messages_per_channel: int = 100,
    max_concurrent_channels: int = 5,
) -> List[discord.Message]:
    # Rate-limited fetching phase
    channel_semaphore = asyncio.Semaphore(max_concurrent_channels)
    
    # Unlimited parallel processing phase
    tasks = [fetch_channel_messages(channel) for channel in channels]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Automatic Retry Logic

HTTP 429 (rate limit) errors trigger exponential backoff:

```python
async def execute_with_rate_limit(self, api_call: Callable) -> Any:
    for attempt in range(self.max_retries + 1):
        try:
            await self.acquire()
            return await api_call()
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = e.retry_after if hasattr(e, "retry_after") else self.retry_delay
                if attempt < self.max_retries:
                    await asyncio.sleep(retry_after)
                    continue
```

### Smart Resumption System

The bot implements intelligent checkpointing to avoid reprocessing messages with per-server status tracking:

```python
async def resume_indexing_from_checkpoints(self) -> bool:
    channels_by_guild = self.get_channels_by_guild()
    overall_total_processed = 0
    
    # Process each server separately with resumption logic
    for guild_id, guild_channels in channels_by_guild.items():
        if not is_server_configured(str(guild_id)):
            continue
            
        # Get resumption info for this server
        server_status = get_server_indexing_status(guild_id)
        
        if server_status['needs_full_processing']:
            # Full historical processing in batches
            for i in range(0, len(guild_channels), 5):
                channel_batch = guild_channels[i:i+5]
                raw_messages = await self.rate_limiter.batch_fetch_messages(
                    channels=channel_batch,
                    messages_per_channel=1000,
                    max_concurrent_channels=5,
                )
                if raw_messages:
                    batch_messages = [self._extract_message_data(msg) for msg in raw_messages]
                    success = await self.send_batch_to_pipeline(batch_messages)
                    
        elif server_status['resumption_recommended']:
            # Resume from last timestamp
            last_timestamp = server_status['last_indexed_timestamp']
            for i in range(0, len(guild_channels), 5):
                channel_batch = guild_channels[i:i+5]
                raw_messages = await self.rate_limiter.batch_fetch_messages_after_timestamp(
                    channels=channel_batch,
                    after_timestamp=last_timestamp,
                    messages_per_channel=1000,
                    max_concurrent_channels=5,
                )
                if raw_messages:
                    batch_messages = [self._extract_message_data(msg) for msg in raw_messages]
                    success = await self.send_batch_to_pipeline(batch_messages)
```

## Message Processing Integration

### Pipeline Coordination Pattern

The bot coordinates with but doesn't implement the message processing pipeline:

```python
# Bot provides coordination, not implementation
class DiscordBot:
    def __init__(self):
        self.pipeline_ready = asyncio.Event()  # Coordination signal
        self.message_pipeline: Optional["MessagePipeline"] = None  # Reference only
```

### Backpressure Management

The system prevents memory overflow through event-based coordination:

```python
# Send batch and wait for completion
self.pipeline_ready.clear()
success = await self.message_pipeline.process_messages(messages)
await self.pipeline_ready.wait()  # Backpressure control
```

### Message Data Extraction

Rich metadata extraction for comprehensive indexing:

```python
def _extract_message_data(self, message: discord.Message) -> Dict[str, Any]:
    return {
        "id": message.id,
        "content": message.content,
        "author": {
            "id": message.author.id,
            "name": message.author.name,
            "display_name": message.author.display_name,
            "bot": message.author.bot,
        },
        "channel": {
            "id": message.channel.id,
            "name": channel_name,
            "type": str(message.channel.type),
            "category_id": getattr(message.channel, 'category_id', None),
        },
        "guild": {
            "id": guild_id,
            "name": guild_name,
            "member_count": getattr(message.guild, 'member_count', None),
        },
        "timestamp": message.created_at.isoformat(),
        "attachments": [att.url for att in message.attachments],
        "has_embeds": len(message.embeds) > 0,
    }
```

## Model Management & Initialization

### Dual Model Architecture

The system supports separate text and vision models for comprehensive processing:

```python
# From main.py initialization
model_manager = ModelManager()
health_results = model_manager.health_check_both_models()

if health_results['both_healthy']:
    logger.info(f"Both models loaded and healthy - "
               f"text:{health_results['text_model']['response_time']:.2f}s, "
               f"vision:{health_results['vision_model']['response_time']:.2f}s")
else:
    # Handle model failures gracefully
    if not health_results['text_model']['healthy']:
        error_msg += f"Text model error: {health_results['text_model']['error']}"
    if not health_results['vision_model']['healthy']:
        error_msg += f"Vision model error: {health_results['vision_model']['error']}"
    raise RuntimeError(error_msg)
```

### Embedding Model Preloading

BGE embeddings are preloaded to prevent runtime blocking:

```python
# Preload embedding models to prevent runtime blocking
try:
    from src.db.embedders import preload_embedder
    await preload_embedder("BAAI/bge-large-en-v1.5")
    logger.info("BGE embedding model preloaded successfully")
except Exception as e:
    logger.warning(f"Failed to preload BGE embedding model: {e}")
    logger.info("BGE model will be loaded on first use (may cause delays)")
```

### Startup Configuration Flow

```python
async def main() -> None:
    # 1. Initialize database and configuration tables
    initialize_db()
    create_config_tables()
    
    # 2. Load configured servers into memory cache
    configured_servers = load_configured_servers()
    
    # 3. Preload embedding models
    await preload_embedder("BAAI/bge-large-en-v1.5")
    
    # 4. Initialize and health check models
    model_manager = ModelManager()
    health_results = model_manager.health_check_both_models()
    
    # 5. Create bot instance and setup handlers
    bot = DiscordBot()
    setup_bot_actions(bot)
    
    # 6. Start bot with proper cleanup handling
    await bot.start(settings.DISCORD_TOKEN)
```

## Configuration & Security

### Bot Permissions & Intents

The bot requires specific intents for comprehensive message access:

```python
# From settings.py
@property
def get_intents(self) -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True    # For reading message content
    intents.guilds = True             # For server information  
    intents.guild_messages = True     # For message events
    intents.members = True            # For member information
    return intents
```

### Security Considerations

1. **Token Protection**: Never log or expose Discord tokens
2. **DM Privacy**: DMs are never indexed or stored
3. **Local Processing**: All AI processing uses local LLM (no external API calls)
4. **User Isolation**: Conversation histories are user-specific

### Command Prefix Configuration

```python
# Configurable command prefix from settings
super().__init__(
    command_prefix=settings.COMMAND_PREFIX,  # Default: "!"
    intents=settings.get_intents,
    help_command=None,  # Custom help system
)
```

## Operational Patterns

### Channel Discovery

```python
def get_all_channels(self) -> List[discord.TextChannel]:
    return [
        channel
        for guild in self.guilds
        for channel in guild.channels
        if isinstance(channel, discord.TextChannel)
    ]

def get_channels_by_guild(self) -> Dict[int, List[discord.TextChannel]]:
    # Group channels by guild for server-specific processing
```

### Server-Specific Processing

The system maintains server separation for data organization:

```python
# Process each server separately with resumption logic
for guild_id, guild_channels in channels_by_guild.items():
    server_status = get_server_indexing_status(guild_id)
    # Server-specific processing strategy
```

### Queue-Based Conversation Handling

Stateless conversation processing through fair queuing:

```python
# Check queue status
if queue.is_user_queued(user_id):
    await ctx.send("Already Processing: Request in queue")
    return

# Add to queue with metadata
success = await queue.add_request(
    user_id=user_id,
    server_id=server.server_id,
    message=message,
    discord_message_id=ctx.message.id,
    discord_channel=ctx.channel
)
```

## Performance & Monitoring

### Status Reporting

```python
@bot.command(name='status')
async def status_command(ctx: commands.Context):
    guild_count = len(bot.guilds)
    channel_count = len(bot.get_all_channels())
    pipeline_status = "Active" if bot.message_pipeline else "Inactive"
    
    queue = get_conversation_queue()
    queue_stats = queue.get_stats()
    # Display comprehensive status
```

### Error Handling Patterns

The bot implements comprehensive error handling with specific exception types:

```python
# Main bot startup error handling
except (discord.LoginFailure, discord.HTTPException, discord.ConnectionClosed,
        ValueError, OSError, RuntimeError, ChromaError, ConnectionError, 
        TimeoutError, KeyError) as e:
    logger.error(f"Failed to start bot: {e}")
    raise

# Message processing error handling
except (discord.HTTPException, discord.Forbidden, discord.NotFound) as e:
    logger.error(f"Discord error handling message: {e}")
except (asyncio.TimeoutError, ConnectionError) as e:
    logger.error(f"Connection error handling message: {e}")

# Rate limiter error handling
except (discord.HTTPException, asyncio.TimeoutError, MemoryError, 
        ValueError, IndexError, RuntimeError) as e:
    logger.error(f"Error during processing: {e}")
    return False

# Command error handling
@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found! Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing required argument! Use `!help` for usage information.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument! Use `!help` for usage information.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Command on cooldown! Try again in {error.retry_after:.1f} seconds.")
    else:
        logger.error(f"Unexpected command error: {error}")
        await ctx.send("An unexpected error occurred! The error has been logged.")
```

### Comprehensive Cleanup System

The bot implements a robust cleanup system with fallback mechanisms:

```python
# Main cleanup flow with fallback
try:
    if cleanup_manager and bot:
        await cleanup_manager.cleanup_all()
except Exception as cleanup_error:
    logger.error(f"Error during cleanup: {cleanup_error}")
    
# Fallback cleanup if cleanup_manager wasn't created
elif bot and not cleanup_manager:
    try:
        if not bot.is_closed():
            await bot.close()
            logger.info("Bot connection closed during fallback cleanup")
    except Exception as fallback_error:
        logger.error(f"Error during fallback cleanup: {fallback_error}")
```

### Logging Strategy

- **Structured logging** with timestamped file output and console display
- **UTF-8 encoding** with Windows compatibility for emoji support
- **Log rotation** with dated filenames (e.g., `discord-indexer-20240924-143052.log`)
- **Performance metrics** for rate limiting, model health checks, and processing times
- **Error tracking** with specific exception types without sensitive data exposure
- **Debug levels** configurable via settings (INFO for DEBUG=false, WARNING for production)

### File System Organization

```python
# Log file structure
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
log_filename = f"discord-indexer-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
log_filepath = os.path.join(logs_dir, log_filename)

# Logging configuration
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filepath, encoding='utf-8'),
        logging.StreamHandler()  # Also log to console
    ]
)
```

## Advanced Features

### Rate Limiter Enhancements

The rate limiter now supports smart resumption with timestamp-based fetching:

```python
async def batch_fetch_messages_after_timestamp(
    self,
    channels: List[discord.TextChannel],
    after_timestamp: str,
    messages_per_channel: int = 1000,
    max_concurrent_channels: int = 5,
) -> List[discord.Message]:
    # Parse timestamp and fetch only newer messages
    after_datetime = datetime.fromisoformat(after_timestamp.replace('Z', '+00:00'))
    
    async for message in channel.history(
        limit=messages_per_channel, 
        oldest_first=True, 
        after=after_datetime
    ):
        messages.append(message)
```

### Message Data Extraction Enhancements

Rich metadata extraction now includes enhanced attachment and embed handling:

```python
def _extract_message_data(self, message: discord.Message) -> Dict[str, Any]:
    return {
        "id": message.id,
        "content": message.content,
        "author": {
            "id": message.author.id,
            "name": message.author.name,
            "display_name": message.author.display_name,
            "global_name": getattr(message.author, 'global_name', None),
            "nick": getattr(message.author, 'nick', None),
            "discriminator": getattr(message.author, 'discriminator', None),
            "bot": message.author.bot,
            "system": getattr(message.author, 'system', False)
        },
        "channel": {
            "id": message.channel.id,
            "name": channel_name,
            "type": str(message.channel.type),
            "category_id": getattr(message.channel, 'category_id', None),
            "position": getattr(message.channel, 'position', None)
        },
        "guild": {
            "id": guild_id,
            "name": guild_name,
            "icon": str(message.guild.icon) if message.guild.icon else None,
            "member_count": getattr(message.guild, 'member_count', None),
            "features": getattr(message.guild, 'features', None)
        },
        "timestamp": message.created_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "pinned": message.pinned,
        "reference": {"message_id": message.reference.message_id} if message.reference else None,
        "attachments": [att.url for att in message.attachments],
        "has_embeds": len(message.embeds) > 0,
        "type": str(message.type),
    }
```

This architecture provides a robust, scalable Discord bot system that efficiently handles message indexing with comprehensive dual-model AI capabilities, smart resumption, advanced rate limiting, and reliable error handling while maintaining clear separation between Discord operations and message processing concerns.