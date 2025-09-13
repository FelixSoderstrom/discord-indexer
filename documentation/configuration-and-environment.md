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
    LLM_MODEL_NAME: str                   # Local LLM model name
    LANGCHAIN_VERBOSE: bool = False       # LangChain debug output
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
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

#### LLM Model Configuration
```bash
# Local LLM model selection
LLM_MODEL_NAME=llama3.1:8b              # Primary model
# Alternative models (commented examples)
# LLM_MODEL_NAME=qwen2.5-coder:32b      # Code-focused model
# LLM_MODEL_NAME=mistral-nemo            # Alternative option
```

#### Optional Ollama Configuration
```bash
# Ollama server configuration (optional)
OLLAMA_HOST=http://localhost:11434       # Custom Ollama host
```

### Environment File Structure

The `.env` file follows a structured format with documentation:

```bash
# NOT USED CURRENTLY
# APPLICATION ID: 1407288437911982201
# PUBLIC KEY: 8f85af9bb6deb5230967db492e93fe069d994cd35c46d52c45bf4a41f17beea2

# Discord Configuration
DISCORD_TOKEN=your_token_here
COMMAND_PREFIX=!

# Development Configuration
DEBUG=True
LANGCHAIN_VERBOSE=false

# Model Configuration
LLM_MODEL_NAME=llama3.1:8b
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
pydantic-settings==2.10.1               # Environment-based settings
python-dotenv==1.1.1                    # Environment file loading
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

### Python Version Requirements

**Target Version**: Python 3.10.6 (specified in project documentation)
**Current System**: Python 3.13.1 (detected during analysis)

**Version Compatibility Notes:**
- Project designed for Python 3.10.6 but compatible with 3.10+
- Current system Python 3.13.1 may require dependency compatibility testing
- Virtual environment recommended for version isolation

### Dependency Installation Process

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# or
venv\Scripts\activate.bat     # Windows CMD

# Install dependencies
pip install -r requirements.txt
```

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

## System Validation

### Database Initialization Validation

The system implements comprehensive database validation during startup:

```python
# Database initialization with error handling
def initialize_db() -> None:
    databases_path = Path(__file__).parent / "databases"
    try:
        databases_path.mkdir(exist_ok=True)
        initialize_conversation_db()
        logger.info("Database directory structure ready")
    except PermissionError as e:
        logger.error(f"Insufficient permissions: {e}")
        raise
    except OSError as e:
        logger.error(f"Failed to create database directory: {e}")
        raise
```

### LLM Model Validation

Automated model availability checking and health validation:

```python
# Model availability validation
def ensure_model_available(model_name: str) -> None:
    client = get_ollama_client()
    models = client.list()
    model_names = [model.get("name") for model in models.get("models", [])]
    
    if model_name not in model_names:
        logger.info(f"Downloading model {model_name}...")
        client.pull(model_name)

# Health check validation
def health_check(model_name: str) -> bool:
    try:
        client = get_ollama_client()
        client.chat(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            options={"num_predict": 10}
        )
        return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False
```

### Discord Connection Validation

Multi-stage Discord connection validation in `main.py`:

```python
# Startup validation sequence
async def main() -> None:
    try:
        # 1. Database initialization
        initialize_db()
        
        # 2. Bot instance creation  
        bot = DiscordBot()
        
        # 3. Event handler setup
        setup_bot_actions(bot)
        
        # 4. Discord connection
        await bot.start(settings.DISCORD_TOKEN)
        
    except (discord.LoginFailure, discord.HTTPException, 
            discord.ConnectionClosed, ValueError, OSError, 
            RuntimeError, ChromaError) as e:
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

The project is optimized for consumer hardware:

```
Target Hardware:
- GPU: RTX 3090 (24GB VRAM)
- RAM: 16GB system memory
- Storage: SSD recommended for database performance
```

### Performance Configuration

#### Model Selection Strategy
```bash
# Primary model (balanced performance/memory)
LLM_MODEL_NAME=llama3.1:8b

# High-performance alternatives
# LLM_MODEL_NAME=qwen2.5-coder:32b    # Code-focused, higher memory
# LLM_MODEL_NAME=qwen2.5:14b-instruct # Instruction-tuned variant
```

#### Memory Management
```python
# Model unloading for memory management
def unload_model_from_memory(model_name: str) -> bool:
    client.chat(
        model=model_name,
        messages=[{"role": "user", "content": "unload"}],
        options={"num_predict": 1},
        keep_alive=0,  # Immediate unload
    )
```

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

- **Memory Usage**: Monitor model loading and ChromaDB memory consumption
- **Disk Space**: Database growth monitoring for large Discord servers
- **Network**: Discord API rate limiting and connection monitoring
- **GPU Utilization**: Local LLM inference monitoring

### Scalability Considerations

- **Server-Specific Databases**: Isolated databases per Discord server prevent cross-contamination
- **Lazy Loading**: Database clients created on-demand to minimize memory footprint
- **Batch Processing**: Rate-limited parallel message fetching for large historical imports
- **Model Caching**: Context window and model metadata caching to reduce overhead

## Troubleshooting Common Issues

### Configuration Validation Failures

1. **Missing Discord Token**
   ```
   Error: Field required [type=missing, input={...}]
   Solution: Ensure DISCORD_TOKEN is set in .env
   ```

2. **Invalid Model Name**
   ```
   Error: Model not found in Ollama
   Solution: Check available models with `ollama list`
   ```

3. **Database Permission Errors**
   ```
   Error: PermissionError on database directory creation
   Solution: Ensure write permissions in project directory
   ```

### Environment Setup Issues

1. **Python Version Compatibility**
   ```
   Target: Python 3.10.6
   Current: Python 3.13.1
   Action: Test compatibility or use pyenv for version management
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