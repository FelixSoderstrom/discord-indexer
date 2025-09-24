# Configuration and Environment Management

## Overview

The Discord-Indexer project implements a robust configuration management system using Pydantic settings, environment-based configuration, and comprehensive validation patterns. This document outlines the configuration architecture, environment setup requirements, dependency management, and system validation strategies.

## Configuration Architecture

### Pydantic Settings Framework

The project uses Pydantic-based settings management through `src/config/settings.py`, providing type-safe configuration with automatic environment variable mapping:

```python
# Core settings structure
class BotSettings(BaseSettings):
    DISCORD_TOKEN: str                    # Required Discord bot token
    COMMAND_PREFIX: str = "!"             # Bot command prefix (default: "!")
    DEBUG: bool = False                   # Debug mode flag (default: False)
    TEXT_MODEL_NAME: str                  # Text processing model
    VISION_MODEL_NAME: str                # Vision processing model
    LANGCHAIN_VERBOSE: bool = False       # LangChain debug output
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"  # Default embedding model
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    
    @property
    def LLM_MODEL_NAME(self) -> str:
        """Backward compatibility property for TEXT_MODEL_NAME."""
        return self.TEXT_MODEL_NAME
```

**Key Features:**
- **Type Safety**: All configuration values are strongly typed with automatic validation
- **Environment Integration**: Automatic loading from `.env` files with case-sensitive matching
- **Default Values**: Sensible defaults for non-critical settings
- **Discord Intents**: Programmatic Discord permission configuration via `get_intents` property

### Settings Instantiation Pattern

Configuration is instantiated at module level for application-wide access:

```python
# Global settings instance
settings = BotSettings()

# Usage throughout application
from src.config.settings import settings
bot_token = settings.DISCORD_TOKEN
```

## Environment Setup

### Required Environment Variables

The following environment variables must be configured in `.env`:

#### Core Discord Configuration
```bash
# Discord bot credentials
DISCORD_TOKEN=your_discord_bot_token_here
COMMAND_PREFIX=!                          # Optional, defaults to "!"
```

#### Development Configuration
```bash
# Debug and development settings
DEBUG=True                               # Enable debug logging
LANGCHAIN_VERBOSE=false                  # LangChain debug output
```

#### Dual Model Configuration
```bash
# Text processing model (for DMAssistant and LinkAnalyzer)
TEXT_MODEL_NAME=llama3.2:3b             # Text model for conversation and analysis

# Vision processing model (for image analysis)
VISION_MODEL_NAME=minicpm-v             # Vision-language model for image processing

# Embedding model for vector similarity search
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

**Model Configuration Notes:**
- **TEXT_MODEL_NAME**: Used by DMAssistant for conversation responses and LinkAnalyzer for web content processing
- **VISION_MODEL_NAME**: Used by image processing pipeline for analyzing uploaded images and screenshots
- **EMBEDDING_MODEL_NAME**: Used for semantic search with server-specific override capability
- **Both models load simultaneously at startup** with 30-minute keep-alive to maintain responsiveness
- **Memory requirement**: Approximately 8-12GB VRAM depending on model sizes
- **Model availability**: Ollama automatically downloads missing models during initialization

#### Optional Ollama Configuration
```bash
# Ollama server configuration (optional)
OLLAMA_HOST=http://localhost:11434       # Custom Ollama host
```

### Environment File Structure

The `.env` file follows a structured format with documentation:

```bash
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
COMMAND_PREFIX=!

# Development Configuration
DEBUG=True
LANGCHAIN_VERBOSE=false

# Dual Model Configuration
TEXT_MODEL_NAME=llama3.2:3b
VISION_MODEL_NAME=minicpm-v
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

## Dependency Management

### Core Dependencies

The project maintains specific version requirements in `requirements.txt`:

#### Discord Integration
```
discord.py==2.6.0                       # Discord API wrapper
```

#### Configuration Management
```
pydantic==2.11.7                        # Type validation and settings
pydantic-settings==2.10.1               # Environment-based settings (includes .env support)
```

#### Database and Vector Storage
```
chromadb==1.0.20                        # Vector database
```

#### LLM Integration
```
ollama>=0.3.0                           # Local LLM interface
langchain-ollama>=0.1.0                 # LangChain Ollama integration
langchain-community>=0.2.0              # LangChain community tools
langchain-core>=0.2.0                   # LangChain core components
langchain>=0.2.0                        # LangChain framework
```

#### Web Scraping and Content Processing
```
trafilatura==2.0.0                      # Web content extraction
lxml_html_clean                         # HTML cleaning utilities
```

#### Machine Learning and Embeddings
```
sentence-transformers>=2.2.0            # Text embeddings for semantic search
torch>=2.0.0                            # PyTorch for ML operations
torchvision                             # Computer vision utilities
torchaudio                              # Audio processing utilities
```

#### Additional Dependencies
```
Pillow>=10.0.0                         # Image processing
requests>=2.31.0                       # HTTP requests
aiohttp>=3.8.0                         # Async HTTP client
```

### Python Version Requirements

**Target Version**: Python 3.10.6 (specified in project documentation)

**Version Compatibility Notes:**
- Project designed for Python 3.10.6 but compatible with 3.10+
- PyTorch CUDA installation requires specific commands (see requirements.txt)
- Virtual environment recommended for dependency isolation

### Dependency Installation Process

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# or
venv\Scripts\activate.bat     # Windows CMD

# Install CUDA-enabled PyTorch (if GPU available)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# Install remaining dependencies
pip install -r requirements.txt
```

**CUDA Installation Notes:**
- The requirements.txt includes CUDA installation instructions
- GPU support recommended for BGE embedding models
- CPU-only installation available but significantly slower

## Security Configuration

### Token Management

The project implements secure token handling patterns:

#### Environment-Based Tokens
- Discord tokens stored exclusively in `.env` files
- Tokens never hardcoded in source code
- `.env` files excluded from version control via `.gitignore`

#### Logging Security
```python
# Secure logging patterns from main.py
logger.info("= Connecting to Discord...")  # No token exposure
# Token passed securely to Discord API
await bot.start(settings.DISCORD_TOKEN)
```

#### Access Control Patterns
```python
# Discord intents configuration
@property
def get_intents(self) -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True    # Required for message indexing
    intents.guilds = True            # Server information access
    intents.guild_messages = True    # Message event handling
    intents.members = True           # Member information (optional)
    return intents
```

### File Permissions and Storage

- Database files created with appropriate permissions via `pathlib.Path`
- Separate database directories per Discord server (`databases/{server_id}/chroma_data`)
- Conversation data isolated in SQLite databases
- Log files written to dedicated `logs/` directory with timestamp-based naming

## Server Configuration System

### Overview

The Discord-Indexer implements a comprehensive server-specific configuration system using SQLite storage and in-memory caching. Each Discord server requires configuration before message processing can begin, including error handling preferences and embedding model selection.

### Server Configuration Architecture

#### SQLite Storage Schema
```sql
CREATE TABLE IF NOT EXISTS server_configs (
    server_id TEXT PRIMARY KEY,
    message_processing_error_handling TEXT DEFAULT 'skip',
    embedding_model_name TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### In-Memory Cache System
```python
# Global cache of configured server IDs for fast lookup
_configured_servers: List[str] = []

def load_configured_servers() -> List[str]:
    """Load all configured server IDs into memory cache."""
    global _configured_servers
    with get_config_db() as conn:
        cursor = conn.execute("SELECT server_id FROM server_configs")
        _configured_servers = [row[0] for row in cursor.fetchall()]
    return _configured_servers

def is_server_configured(server_id: str) -> bool:
    """Check if server is configured using in-memory cache."""
    return server_id in _configured_servers
```

### Terminal UI Configuration Process

When unconfigured servers are detected, the system launches an interactive terminal UI:

#### Error Handling Configuration
```
🤖 CONFIGURING SERVER: ServerName
   Server ID: 1234567890

When a message fails to process, should the bot:
1. Skip that message and continue with others (recommended)
2. Stop processing and shut down the application

Enter choice for ServerName (1 or 2):
```

#### Embedding Model Selection
```
🧠 EMBEDDING MODEL CONFIGURATION
Choose the embedding model for semantic search:
1. Use global default (recommended)
2. Use BGE-large-en-v1.5 (high accuracy, requires GPU)
3. Use lightweight model (faster, less accurate)
4. Custom model name

Enter choice for ServerName (1-4):
```

### Server Configuration Workflow

#### Startup Configuration
```python
# Called during bot startup in on_ready_handler
def configure_all_servers(guilds) -> bool:
    """Configure all unconfigured servers at startup."""
    unconfigured_servers = []
    
    # Find servers that need configuration
    for guild in guilds:
        server_id = str(guild.id)
        if not is_server_configured(server_id):
            unconfigured_servers.append((server_id, guild.name))
    
    # Run interactive configuration for each server
    for server_id, server_name in unconfigured_servers:
        success = configure_new_server(server_id, server_name)
        if success:
            add_server_to_cache(server_id)
```

#### Runtime Validation
```python
# Called before processing any server message
def ensure_server_configured(server_id: str, server_name: str) -> bool:
    """Ensure server is configured before processing messages."""
    if is_server_configured(server_id):
        return True
    
    # Run configuration process if not configured
    return configure_new_server(server_id, server_name)
```

### Per-Server Embedding Models

Servers can override the global embedding model setting:

```python
def get_server_embedding_model(server_id: int) -> Optional[str]:
    """Get the configured embedding model for a server."""
    with get_config_db() as conn:
        cursor = conn.execute(
            "SELECT embedding_model_name FROM server_configs WHERE server_id = ?",
            (str(server_id),)
        )
        row = cursor.fetchone()
        if row and row[0] and row[0] != "default":
            return row[0]
    return None
```

### Database Integration

Server configurations integrate with ChromaDB client creation:

```python
def get_db(server_id: int, embedding_model: Optional[str] = None) -> Client:
    """Get ChromaDB client with server-specific embedding model."""
    # Check for server-specific embedding model override
    if not embedding_model:
        embedding_model = get_server_embedding_model(server_id)
    
    # Create cache key including embedding model
    cache_key = f"{server_id}_{embedding_model or 'default'}"
    
    if cache_key in _clients:
        return _clients[cache_key]
    
    # Create server-specific database with proper embedding model
    server_db_path = Path(__file__).parent / "databases" / str(server_id) / "chroma_data"
    client = chromadb.PersistentClient(path=str(server_db_path))
    _clients[cache_key] = client
    return client
```

## System Validation

### Database Initialization Validation

The system implements comprehensive database validation during startup:

```python
# Database initialization with error handling
def initialize_db() -> None:
    databases_path = Path(__file__).parent / "databases"
    try:
        databases_path.mkdir(exist_ok=True)
        # Initialize conversation database
        initialize_conversation_db()
        # Initialize server configuration database
        _initialize_config_db()
        logger.info("Database directory structure ready")
    except PermissionError as e:
        logger.error(f"Insufficient permissions: {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to create database directory: {e}")
        raise
```

### Dual Model Validation and Loading

The system implements simultaneous loading and health checking of both text and vision models via ModelManager:

```python
# Dual model manager initialization
class ModelManager:
    def __init__(self) -> None:
        self._text_model_name = settings.TEXT_MODEL_NAME
        self._vision_model_name = settings.VISION_MODEL_NAME
        self._models_loaded = False
        self.ensure_models_loaded()  # Load both models simultaneously

# Simultaneous model loading with keep-alive
def ensure_models_loaded(self) -> None:
    # Download models if not available
    ensure_model_available(self._vision_model_name)
    ensure_model_available(self._text_model_name)
    
    # Load vision model into memory first
    client = get_ollama_client()
    client.chat(
        model=self._vision_model_name,
        messages=[{"role": "user", "content": "Hello"}],
        options={"num_predict": 10},
        keep_alive="30m"
    )
    
    # Load text model into memory second  
    client.chat(
        model=self._text_model_name,
        messages=[{"role": "user", "content": "Hello"}],
        options={"num_predict": 10},
        keep_alive="30m"
    )
    
    self._models_loaded = True

# Health check both models with detailed results
def health_check_both_models(self) -> Dict[str, Any]:
    text_healthy = health_check(self._text_model_name)
    vision_healthy = health_check(self._vision_model_name)
    return {
        'text_model': {
            'healthy': text_healthy,
            'response_time': text_time,
            'error': None if text_healthy else f"Text model health check failed"
        },
        'vision_model': {
            'healthy': vision_healthy, 
            'response_time': vision_time,
            'error': None if vision_healthy else f"Vision model health check failed"
        },
        'both_healthy': text_healthy and vision_healthy,
        'total_check_time': total_time
    }
```

**Model Loading Architecture:**
- **Startup Sequence**: Both models load during application initialization, not on-demand
- **Memory Persistence**: 30-minute keep-alive prevents Ollama from unloading models
- **Failure Handling**: System fails hard if either model cannot load - no fallback logic
- **Health Monitoring**: Periodic checks ensure both models remain responsive

### Discord Connection Validation

Multi-stage Discord connection validation in `main.py`:

```python
# Startup validation sequence
async def main() -> None:
    try:
        # 1. Database and configuration initialization
        initialize_db()
        create_config_tables()
        
        # 2. Load configured servers into memory cache
        configured_servers = load_configured_servers()
        
        # 3. Preload embedding models
        from src.db.embedders import preload_embedder
        await preload_embedder("BAAI/bge-large-en-v1.5")
        
        # 4. Initialize ModelManager and health check
        model_manager = ModelManager()
        health_results = model_manager.health_check_both_models()
        
        # 5. Bot instance creation and setup
        bot = DiscordBot()
        setup_bot_actions(bot)
        
        # 6. Discord connection
        await bot.start(settings.DISCORD_TOKEN)
        
    except (discord.LoginFailure, discord.HTTPException, 
            discord.ConnectionClosed, ValueError, OSError, 
            RuntimeError, ChromaError, ConnectionError, TimeoutError, KeyError) as e:
        logger.error(f"Failed to start bot: {e}")
        raise
```

## Exception Handling Patterns

### Configuration-Specific Exceptions

The project implements targeted exception handling for configuration issues:

#### Pydantic Validation Errors
- Automatic validation of environment variables during settings instantiation
- Type conversion errors caught and reported with specific field information
- Missing required values trigger clear error messages

#### Database Connection Errors
```python
# Specific ChromaDB error handling
try:
    client = chromadb.PersistentClient(path=str(server_db_path))
except ChromaError as e:
    logger.error(f"ChromaDB initialization failed: {e}")
    raise
except (TypeError, ImportError, RuntimeError, AttributeError) as e:
    logger.error(f"Unexpected error during ChromaDB initialization: {e}")
    raise
```

#### Message Processing Exceptions
```python
# Custom message processing exception
class MessageProcessingError(Exception):
    """Exception for message processing pipeline failures"""
    def __init__(self):
        logger.warning("Message processing failed.")
```

### Error Recovery Patterns

- **Database Initialization**: Graceful failure with clear error reporting
- **Model Loading**: Automatic model downloading on missing models
- **Discord Connection**: Specific error types for different failure modes
- **Message Processing**: Individual message failure doesn't stop pipeline

## Hardware Requirements and Optimization

### Target System Specifications

The project is optimized for consumer hardware with dual model requirements:

```
Target Hardware:
- GPU: RTX 3090 (24GB VRAM) or equivalent
- VRAM Usage: 8-12GB for simultaneous text + vision models
- RAM: 24GB system memory (increased for dual model operation)
- Storage: SSD recommended for database performance
```

**Dual Model Memory Requirements:**
- **Text Model (llama3.2:3b)**: ~2-3GB VRAM
- **Vision Model (minicpm-v)**: ~4-6GB VRAM
- **ChromaDB**: ~2-4GB system RAM
- **Discord Operations**: ~1-2GB system RAM
- **Total Estimated**: 8-12GB VRAM + 8-12GB system RAM active usage

### Performance Configuration

#### Dual Model Selection Strategy
```bash
# Text processing model - optimized for conversation and analysis
TEXT_MODEL_NAME=llama3.2:3b           # Lightweight, fast responses for DMAssistant
# TEXT_MODEL_NAME=llama3.1:8b          # Higher quality for complex text analysis
# TEXT_MODEL_NAME=qwen2.5-coder:32b    # Code-focused tasks (high memory)

# Vision processing model - optimized for image understanding
VISION_MODEL_NAME=minicpm-v           # Balanced vision-language model
# VISION_MODEL_NAME=llama3.2-vision:11b # Alternative vision model
# VISION_MODEL_NAME=qwen2.5vl:7b        # Higher quality vision processing
```

**Model Selection Considerations:**
- **Text Model**: Prioritize response speed for interactive conversations (DMAssistant)
- **Vision Model**: Balance accuracy and inference speed for image processing
- **Memory Constraints**: Both models must fit simultaneously in available VRAM
- **Tool Calling**: Text model must support function calling for LinkAnalyzer features

#### Dual Model Memory Management
```python
# Simultaneous model memory management
class ModelManager:
    def ensure_models_loaded(self) -> None:
        # Both models loaded with persistent keep-alive
        vision_memory = self._load_model_persistent(self._vision_model_name)
        text_memory = self._load_model_persistent(self._text_model_name)
        
    def _load_model_persistent(self, model_name: str) -> None:
        client.chat(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            options={"num_predict": 10},
            keep_alive="30m"  # Persistent loading
        )
```

**Memory Management Strategy:**
- **No Dynamic Unloading**: Both models remain loaded for application lifetime
- **Keep-Alive Setting**: 30-minute timeout prevents automatic unloading
- **VRAM Requirements**: Plan for 8-12GB VRAM usage depending on model sizes
- **System Memory**: Additional 4-8GB system RAM for ChromaDB and Discord operations

#### Context Window Detection
```python
# Automatic context window detection with caching
def get_model_max_context(model_name: str) -> int:
    # Special cases for models with incorrect metadata
    if "mistral-nemo" in model_name.lower():
        return 100000  # Corrected context window
    
    # Dynamic detection via ollama show command
    result = subprocess.run(['ollama', 'show', model_name])
    context_match = re.search(r'context\s+length[:\s]+(\d+)', result.stdout)
```

## Deployment Considerations

### Production Environment Setup

1. **Environment Isolation**
   ```bash
   # Use dedicated virtual environment
   python -m venv production_env
   source production_env/Scripts/activate
   ```

2. **Secure Token Management**
   ```bash
   # Production .env configuration
   DISCORD_TOKEN=production_token_here
   DEBUG=False
   LANGCHAIN_VERBOSE=false
   TEXT_MODEL_NAME=llama3.2:3b
   VISION_MODEL_NAME=minicpm-v
   ```

3. **Database Persistence**
   ```bash
   # Ensure database directory permissions
   chmod 755 src/db/databases
   # Backup strategy for ChromaDB and conversation data
   ```

4. **Logging Configuration**
   ```python
   # Production logging (from main.py)
   log_level = logging.INFO if settings.DEBUG else logging.WARNING
   log_filename = f"discord-indexer-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
   ```

### Resource Monitoring

- **Memory Usage**: Monitor dual model loading (8-12GB VRAM) and ChromaDB memory consumption
- **Disk Space**: Database growth monitoring for large Discord servers (per-server ChromaDB + SQLite)
- **Network**: Discord API rate limiting and connection monitoring
- **GPU Utilization**: Local LLM inference monitoring for both text and vision models
- **Configuration Database**: Monitor server_configs.db growth and conversation history

### Scalability Considerations

- **Server-Specific Databases**: Isolated ChromaDB databases per Discord server prevent cross-contamination
- **Server Configuration Cache**: In-memory cache for fast server configuration validation
- **Lazy Loading**: Database clients created on-demand with embedding model-specific caching
- **Batch Processing**: Rate-limited parallel message fetching for large historical imports
- **Model Caching**: Context window and model metadata caching to reduce overhead
- **Per-Server Embedding Models**: Override global embedding model on a per-server basis

## Troubleshooting Common Issues

### Configuration Validation Failures

1. **Missing Discord Token**
   ```
   Error: Field required [type=missing, input={...}]
   Solution: Ensure DISCORD_TOKEN is set in .env
   ```

2. **Invalid Model Names**
   ```
   Error: Text model not found in Ollama
   Solution: Check available models with `ollama list`
   Verify both TEXT_MODEL_NAME and VISION_MODEL_NAME are correct
   ```
   
3. **Insufficient VRAM for Dual Models**
   ```
   Error: Failed to load models simultaneously
   Solution: Use smaller models or increase VRAM
   Consider llama3.2:1b for text or lighter vision models
   ```

4. **Server Configuration Issues**
   ```
   Error: Server not configured for message processing
   Solution: Ensure configure_all_servers() runs at startup
   Check server_configs.db for missing entries
   ```
   
5. **Database Permission Errors**
   ```
   Error: PermissionError on database directory creation
   Solution: Ensure write permissions in project directory
   ```

### Environment Setup Issues

1. **Python Version Compatibility**
   ```
   Target: Python 3.10.6
   Action: Use virtual environment for isolation
   Verify PyTorch CUDA installation if using GPU
   ```

2. **Dependency Conflicts**
   ```
   Solution: Use fresh virtual environment
   pip install --force-reinstall -r requirements.txt
   ```

3. **Ollama Connection Issues**
   ```
   Error: ConnectionError to Ollama
   Solution: Ensure Ollama is running (ollama serve)
   Check OLLAMA_HOST environment variable
   ```

## Best Practices Summary

### Configuration Management
- Use environment variables for all sensitive configuration
- Implement type-safe configuration with Pydantic
- Provide sensible defaults for optional settings
- Document all configuration options clearly

### Security
- Never commit tokens or credentials to version control
- Use case-sensitive environment variable matching
- Implement secure logging practices (no token exposure)
- Separate configuration by environment (dev/prod)

### Error Handling
- Catch specific exceptions rather than broad Exception types
- Provide clear error messages with actionable information
- Implement graceful degradation where possible
- Log errors with appropriate detail levels

### Performance
- Use lazy loading for resource-intensive components
- Implement caching for frequently accessed data
- Monitor and optimize memory usage for large models
- Design for horizontal scaling across Discord servers

This comprehensive configuration and environment management system ensures reliable, secure, and performant operation of the Discord-Indexer project across different deployment scenarios.