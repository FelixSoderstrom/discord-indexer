# src/config/settings.py Documentation

## Purpose
Centralized configuration management using Pydantic for environment-based settings and Discord intents configuration.

## What It Does
1. **Environment Configuration**: Loads bot settings from `.env` file
2. **Discord Intents**: Provides properly configured Discord permissions
3. **Validation**: Uses Pydantic for automatic type validation and environment parsing

## Configuration Settings

### Required Settings
- **`DISCORD_TOKEN`**: Discord bot authentication token (required)

### Optional Settings
- **`COMMAND_PREFIX`**: Bot command prefix (default: "!")
- **`DEBUG`**: Debug mode flag (default: False)

### Discord Intents Property
```python
@property
def get_intents(self) -> discord.Intents:
    """Configure Discord intents for message reading and server access."""
```

**Enabled Intents:**
- `message_content = True` - Read message text content
- `guilds = True` - Access server information
- `guild_messages = True` - Receive message events
- `members = True` - Access member information

## Usage

### Environment File (.env)
```env
DISCORD_TOKEN=your_bot_token_here
COMMAND_PREFIX=!
DEBUG=false
```

### Code Usage
```python
from src.config.settings import settings

# Access configuration
token = settings.DISCORD_TOKEN
prefix = settings.COMMAND_PREFIX

# Get Discord intents
intents = settings.get_intents
```

## Design Decisions

### Why Pydantic?
- **Type Safety**: Automatic validation of environment variables
- **Documentation**: Self-documenting configuration with type hints
- **Extensibility**: Easy to add new configuration options

### Why Property for Intents?
- **Separation of Concerns**: Discord permissions belong in configuration, not bot logic
- **Future Flexibility**: Could make intents configurable via environment variables
- **Clean Architecture**: Keeps Discord-specific imports contained in config module

## Security Considerations
- **Token Storage**: Never commit `.env` file to version control
- **Environment Variables**: Tokens loaded from environment, not hardcoded
- **Permissions**: Intents configured for minimal required access

## Future Extensibility
This configuration structure is ready for:
- Database connection strings
- API keys for external services
- LLM model configurations
- ChromaDB settings
- Logging levels and destinations
