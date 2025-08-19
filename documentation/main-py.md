# main.py Documentation

## Purpose
Entry point and orchestrator for the Discord message indexer bot. Coordinates all components and handles bot lifecycle.

## What It Does
1. **Configuration Loading**: Loads settings from environment variables
2. **Bot Initialization**: Creates DiscordBot instance with proper configuration
3. **Event Handler Setup**: Registers message capture event handlers
4. **Connection Management**: Starts bot connection and handles graceful shutdown

## Key Components

### Main Function Flow
```python
async def main():
    # 1. Setup logging based on DEBUG setting
    # 2. Create DiscordBot instance
    # 3. Setup event handlers via setup_bot_actions()
    # 4. Start bot with Discord token
```

### Error Handling
- **KeyboardInterrupt**: Graceful shutdown when user stops bot
- **General Exceptions**: Logs startup errors and closes bot properly
- **Connection Issues**: Handles Discord API connection failures

## Dependencies
- `src.config.settings` - Bot configuration and Discord token
- `src.bot.client` - DiscordBot class
- `src.bot.actions` - Event handler registration

## Environment Requirements
- `.env` file with `DISCORD_TOKEN`
- Valid Discord bot token with proper permissions

## Usage
```bash
python main.py
```

## Console Output
- Startup sequence with visual separators
- Bot connection status
- Error messages if startup fails
- Graceful shutdown messages

## Future Extensibility
- Ready to add additional services (database, API)
- Logging configuration can be expanded
- Error handling can be enhanced for production use
