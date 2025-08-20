# src/bot/client.py Documentation

## Purpose
Core Discord bot implementation that handles connection, message processing pipeline integration, and data extraction functionality.

## What It Does
1. **Discord Connection**: Manages bot connection with proper intents and configuration
2. **Pipeline Integration**: Hosts message processing pipeline for real-time message handling
3. **Message Storage**: In-memory storage of extracted messages for validation (legacy/fallback)
4. **Historical Processing**: Fetches all existing messages from accessible channels
5. **Data Extraction**: Converts Discord messages to structured data format

## Class: DiscordBot

### Initialization
- Inherits from `commands.Bot` for Discord.py functionality
- Configures command prefix from settings
- Sets up Discord intents for message access
- Initializes storage containers for messages and channel tracking
- Prepares message processing pipeline attribute (initialized later)

### Storage Attributes
```python
self.stored_messages: List[Dict[str, Any]] = []       # All captured messages (legacy/fallback)
self.processed_channels: List[int] = []               # Channels that have been indexed
self.message_pipeline: Optional[MessagePipeline] = None  # Message processing pipeline
```

## Key Methods

### `get_all_channels()`
- **Purpose**: Discovers all accessible text channels across connected servers
- **Returns**: List of Discord TextChannel objects
- **Filters**: Only includes text channels (excludes voice, categories, etc.)

### `get_channel_messages(channel_id, limit=100)`
- **Purpose**: Fetches historical messages from a specific channel
- **Parameters**: 
  - `channel_id`: Discord channel ID
  - `limit`: Maximum messages to fetch (default 100, can be up to 1000)
- **Error Handling**: 
  - Missing permissions
  - Invalid channel IDs
  - API rate limits
- **Returns**: List of extracted message data dictionaries

### `get_all_historical_messages()`
- **Purpose**: Main historical processing function
- **Process**:
  1. Discovers all accessible channels
  2. Fetches messages from each channel
  3. Stores results in `self.stored_messages`
  4. Tracks processed channels
- **Output**: Console progress updates and sample message display

### `_extract_message_data(message)`
- **Purpose**: Converts Discord Message object to structured data
- **Used By**: Both historical processing and real-time pipeline processing
- **Extracts**:
  - Message ID and content
  - Author information (ID, username, display name)
  - Channel information (ID, name)
  - Server/guild information
  - Timestamp (ISO format)
  - Attachment URLs
  - Embed presence
  - Message type

### `close()`
- **Purpose**: Clean shutdown of bot connection with proper resource cleanup
- **Process**:
  1. **Pipeline Cleanup**: Clears message pipeline reference if available
  2. **Parent Cleanup**: Calls parent class close() method for Discord connection
- **Resource Safety**: Ensures proper cleanup of both pipeline and Discord resources

## Message Data Structure
```python
{
    'id': 123456789,                           # Discord message ID
    'content': "Hello world!",                 # Message text content
    'author': {
        'id': 789,                             # Author's Discord ID
        'name': 'username',                    # Author's username
        'display_name': 'Display Name'         # Author's display name
    },
    'channel': {
        'id': 456,                             # Channel ID
        'name': 'general'                      # Channel name
    },
    'guild': {
        'id': 123,                             # Server ID
        'name': 'My Server'                    # Server name
    },
    'timestamp': '2024-01-01T12:00:00',        # ISO timestamp
    'attachments': ['https://cdn.discord.com/...'], # Attachment URLs
    'has_embeds': False,                       # Whether message has embeds
    'message_type': 'default'                  # Discord message type
}
```

## Error Handling
- **Discord.Forbidden**: Logs permission issues but continues processing
- **Invalid Channels**: Safely skips channels that can't be accessed
- **API Errors**: Logs errors but doesn't crash the bot

## Design Decisions

### Why Pipeline Integration at Bot Level?
- **Single Responsibility**: Bot handles Discord connection, pipeline handles processing
- **Clean Separation**: Discord concerns separated from message processing logic
- **Resource Management**: Bot manages pipeline lifecycle alongside Discord connection

### Why Optional Pipeline Attribute?
- **Initialization Order**: Pipeline created after bot is fully connected and ready
- **Type Safety**: Optional typing indicates pipeline may not be available during startup
- **Graceful Shutdown**: Pipeline can be cleared independently during shutdown

### Why In-Memory Storage Retention?
- **Legacy Support**: Maintains compatibility with existing functionality
- **Debugging**: Direct access to captured data for verification and testing
- **Fallback Capability**: Provides backup storage mechanism if needed

### Why Historical-First Processing?
- **Complete Picture**: Gets all existing context before monitoring new messages
- **Resume Capability**: Tracks processed channels for future resume functionality
- **User Experience**: Shows immediate results from message capture

## Future Extensibility
This implementation is designed for easy extension:
- **Pipeline Enhancement**: Message processing pipeline can be extended with additional modules
- **Database Integration**: Historical processing can integrate with pipeline storage
- **Filtering**: Channel discovery can be extended with filtering criteria
- **Pagination**: Message fetching already handles Discord's pagination requirements
- **Multi-Pipeline Support**: Architecture supports multiple specialized pipelines

## Performance Considerations
- **Rate Limiting**: Respects Discord API rate limits
- **Memory Usage**: Stores messages in memory (suitable for small-medium servers)
- **Channel Limits**: Fetches up to 1000 messages per channel (Discord API limit)
- **Pipeline Integration**: Message processing offloaded to dedicated pipeline architecture
- **Resource Management**: Pipeline lifecycle managed alongside Discord connection
