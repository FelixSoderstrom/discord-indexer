"""Metadata preparation and processing for Discord messages.

Handles organization and preparation of message metadata for database storage,
including transformation of Discord-specific data structures into normalized formats.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


def prepare_author_metadata(author_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare author metadata for database storage.
    
    Args:
        author_data: Author information from Discord message
        
    Returns:
        Normalized author metadata dictionary
    """
    return {
        'author_id': author_data.get('id'),
        'author_name': author_data.get('name'),
        'author_display_name': author_data.get('display_name'),
        'author_discriminator': author_data.get('discriminator'),
        'author_bot': author_data.get('bot', False),
        'author_system': author_data.get('system', False)
    }


def prepare_channel_metadata(channel_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare channel metadata for database storage.
    
    Args:
        channel_data: Channel information from Discord message
        
    Returns:
        Normalized channel metadata dictionary
    """
    return {
        'channel_id': channel_data.get('id'),
        'channel_name': channel_data.get('name'),
        'channel_type': channel_data.get('type', 'text'),
        'channel_category': channel_data.get('category_id'),
        'channel_position': channel_data.get('position')
    }


def prepare_guild_metadata(guild_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Prepare guild metadata for database storage.
    
    Args:
        guild_data: Guild information from Discord message
        
    Returns:
        Normalized guild metadata dictionary, None for DM messages
    """
    if not guild_data or not guild_data.get('id'):
        return None
    
    return {
        'guild_id': guild_data.get('id'),
        'guild_name': guild_data.get('name'),
        'guild_icon': guild_data.get('icon'),
        'guild_member_count': guild_data.get('member_count'),
        'guild_features': guild_data.get('features', [])
    }


def prepare_message_metadata(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare core message metadata for database storage.
    
    Args:
        message_data: Complete message data dictionary
        
    Returns:
        Normalized message metadata dictionary
    """
    # Parse timestamp
    timestamp = message_data.get('timestamp')
    parsed_timestamp = None
    if timestamp:
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            logger.warning(f"Failed to parse timestamp: {timestamp}")
    
    # Extract reply information
    reply_to_id = None
    reference = message_data.get('reference')
    if reference:
        reply_to_id = reference.get('message_id')
    
    return {
        'message_id': message_data.get('id'),
        'content': message_data.get('content', ''),
        'content_length': len(message_data.get('content', '')),
        'timestamp': parsed_timestamp,
        'message_type': message_data.get('type', 'default'),
        'has_attachments': len(message_data.get('attachments', [])) > 0,
        'attachment_count': len(message_data.get('attachments', [])),
        'has_embeds': message_data.get('has_embeds', False),
        'is_edited': message_data.get('edited_at') is not None,
        'is_pinned': message_data.get('pinned', False),
        'reply_to_message_id': reply_to_id
    }


def process_message_metadata(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process and organize all metadata for a message.
    
    Coordinates preparation of all metadata components for database storage.
    
    Args:
        message_data: Complete message data dictionary
        
    Returns:
        Dictionary containing organized metadata
    """
    
    metadata_results = {
        'message_metadata': prepare_message_metadata(message_data),
        'author_metadata': prepare_author_metadata(message_data.get('author', {})),
        'channel_metadata': prepare_channel_metadata(message_data.get('channel', {})),
        'guild_metadata': prepare_guild_metadata(message_data.get('guild', {})),
        'processing_metadata': {
            'processed_at': datetime.utcnow(),
            'processor_version': 'v1.0.0',
            'processing_status': 'prepared'
        }
    }
    
    return metadata_results

