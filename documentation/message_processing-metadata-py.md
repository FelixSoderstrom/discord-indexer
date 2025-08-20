# message_processing/metadata.py

## Purpose

Metadata preparation and processing for Discord messages. Handles organization and preparation of message metadata for database storage, including transformation of Discord-specific data structures into normalized formats suitable for indexing and search.

## Key Functions

### Core Metadata Processing

**prepare_author_metadata(author_data)**
- Processes Discord author information into normalized format
- Handles user ID, name, display name, and user type detection
- Prepares author data for database storage and relationship tracking
- Returns structured author metadata dictionary

**prepare_channel_metadata(channel_data)**
- Processes Discord channel information into normalized format
- Handles channel ID, name, type, and organizational structure
- Prepares channel context for message categorization
- Returns structured channel metadata dictionary

**prepare_guild_metadata(guild_data)**
- Processes Discord guild (server) information into normalized format
- Handles guild ID, name, and server-specific metadata
- Manages None values for DM messages (no guild context)
- Returns structured guild metadata dictionary or None for DMs

**prepare_message_metadata(message_data)**
- Processes core message information into normalized format
- Handles message ID, content, timestamps, and message characteristics
- Parses ISO timestamps into proper datetime objects
- Returns structured message metadata dictionary

### Processing Coordination

**process_message_metadata(message_data)**
- Main entry point for metadata processing
- Coordinates all metadata preparation functions
- Processes complete message data from Discord extraction
- Returns comprehensive metadata results with processing information

## Output Structure

### Metadata Results Format
```python
{
    'message_metadata': {
        'message_id': int,
        'content': str,
        'content_length': int,
        'timestamp': datetime,
        'message_type': str,
        'has_attachments': bool,
        'attachment_count': int,
        'has_embeds': bool,
        'is_edited': bool,
        'is_pinned': bool,
        'reply_to_message_id': int or None
    },
    'author_metadata': {
        'author_id': int,
        'author_name': str,
        'author_display_name': str,
        'author_discriminator': str or None,
        'author_bot': bool,
        'author_system': bool
    },
    'channel_metadata': {
        'channel_id': int,
        'channel_name': str,
        'channel_type': str,
        'channel_category': str or None,
        'channel_position': int or None
    },
    'guild_metadata': {
        'guild_id': int,
        'guild_name': str,
        'guild_icon': str or None,
        'guild_member_count': int or None,
        'guild_features': [str]
    } or None,
    'processing_metadata': {
        'processed_at': datetime,
        'processor_version': str,
        'processing_status': str
    }
}
```

## Current Implementation Status

**Architecture:** Fully implemented with proper data normalization
**Timestamp Processing:** Fully implemented with ISO parsing and datetime conversion
**Data Validation:** Implemented with graceful handling of missing data
**Metadata Organization:** Fully implemented with structured output
**Processing Coordination:** Fully implemented with comprehensive metadata tracking

### Implementation Features
- Proper timestamp parsing from ISO format to datetime objects
- Graceful handling of None values (especially for DM messages without guilds)
- Content length calculation and attachment/embed detection
- Processing timestamp and version tracking for audit purposes

## Integration

### Input Sources
- Receives processed message data from pipeline coordinator
- Handles Discord message data extracted by `client.py`
- Processes all Discord-specific data structures

### Output Destinations
- Metadata results passed to storage coordination
- Normalized data prepared for database storage
- Structured format ready for indexing and search operations

## Data Handling

### Discord-Specific Processing
- Transforms Discord snowflake IDs to proper integer format
- Handles Discord timestamp formats and timezone information
- Processes Discord-specific message types and characteristics
- Manages guild vs DM message context differences

### Database Preparation
- Normalizes data for consistent database storage
- Prepares separate metadata categories for optimized querying
- Maintains data relationships for efficient retrieval
- Structures data for both transactional and analytical use cases

## Future Enhancement

Ready for extended metadata capabilities:
- Advanced message relationship tracking (replies, threads)
- Enhanced user and guild context information
- Message edit history and version tracking
- Rich metadata for specialized message types
- Performance optimization for high-volume processing
