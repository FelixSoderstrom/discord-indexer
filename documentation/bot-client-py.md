# src/bot/client.py Documentation

## Purpose
Core Discord bot implementation that handles connection, message storage, and data extraction functionality.

## What It Does
1. **Discord Connection**: Manages bot connection with proper intents and configuration
2. **Message Storage**: In-memory storage of extracted messages for validation
3. **Historical Processing**: Fetches all existing messages from accessible channels
4. **Data Extraction**: Converts Discord messages to structured data format

## Class: DiscordBot

### Initialization
- Inherits from `commands.Bot` for Discord.py functionality
- Configures command prefix from settings
- Sets up Discord intents for message access
- Initializes storage containers for messages and channel tracking

### Storage Attributes
```python
self.stored_messages: List[Dict[str, Any]] = []  # All captured messages
self.processed_channels: List[int] = []          # Channels that have been indexed
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
- **Extracts**:
  - Message ID and content
  - Author information (ID, username, display name)
  - Channel information (ID, name)
  - Server/guild information
  - Timestamp (ISO format)
  - Attachment URLs
  - Embed presence
  - Message type

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

### Why In-Memory Storage?
- **Foundation Phase**: Simple validation of message capture functionality
- **Easy Replacement**: List structure easily replaceable with database later
- **Debugging**: Direct access to captured data for verification

### Why Historical-First Processing?
- **Complete Picture**: Gets all existing context before monitoring new messages
- **Resume Capability**: Tracks processed channels for future resume functionality
- **User Experience**: Shows immediate results from message capture

## Future Extensibility
This implementation is designed for easy extension:
- **Database Integration**: `stored_messages` list easily replaced with database calls
- **Processing Pipeline**: Message extraction can pipe to additional processing steps
- **Filtering**: Channel discovery can be extended with filtering criteria
- **Pagination**: Message fetching already handles Discord's pagination requirements

## Performance Considerations
- **Rate Limiting**: Respects Discord API rate limits
- **Memory Usage**: Stores messages in memory (suitable for small-medium servers)
- **Channel Limits**: Fetches up to 1000 messages per channel (Discord API limit)
