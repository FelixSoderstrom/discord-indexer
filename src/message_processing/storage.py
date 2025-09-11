"""ChromaDB storage for processed Discord messages.

Stores message content with metadata in ChromaDB collections. 
ChromaDB automatically handles text embeddings for semantic search.
"""

import logging
from typing import Dict, Any, Optional

from src.db import get_db


logger = logging.getLogger(__name__)


def store_complete_message(processed_data: Dict[str, Any]) -> bool:
    """Store message in ChromaDB collection with automatic embeddings.
    
    Args:
        processed_data: Complete processed message data
        
    Returns:
        True if storage successful, False otherwise
    """
    # Extract components
    metadata = processed_data.get('metadata', {})
    extractions = processed_data.get('extractions', {})
    
    message_metadata = metadata.get('message_metadata', {})
    guild_metadata = metadata.get('guild_metadata', {})
    author_metadata = metadata.get('author_metadata', {})
    channel_metadata = metadata.get('channel_metadata', {})
    
    message_id = message_metadata.get('message_id')
    server_id = guild_metadata.get('guild_id')
    
    if not message_id:
        logger.error("No message ID found in processed data")
        return False
    
    if not server_id:
        logger.error("No server ID found in processed data")
        return False
    
    try:
        # Get ChromaDB client for this server
        db_client = get_db(server_id)
        
        # Get or create messages collection
        collection_name = "messages"
        try:
            collection = db_client.get_collection(collection_name)
        except Exception:
            collection = db_client.create_collection(collection_name)
            logger.info(f"Created collection '{collection_name}' for server {server_id}")
        
        # Prepare document content (message text + link summaries)
        document_content = message_metadata.get('content', '')
        
        # Add link summaries if available
        if extractions and extractions.get('link_summaries_combined'):
            link_summaries = extractions['link_summaries_combined']
            if document_content:
                document_content = f"{document_content}\n\n{link_summaries}"
            else:
                document_content = link_summaries
        
        # Skip empty messages
        if not document_content.strip():
            logger.info(f"Skipping empty message {message_id}")
            return True
        
        # Prepare metadata for ChromaDB
        chroma_metadata = {
            'message_id': str(message_id),
            'author_id': str(author_metadata.get('author_id', '')),
            'author_name': str(author_metadata.get('author_name', '')),
            'channel_id': str(channel_metadata.get('channel_id', '')),
            'channel_name': str(channel_metadata.get('channel_name', '')),
            'guild_id': str(server_id),
            'guild_name': str(guild_metadata.get('guild_name', '')),
            'timestamp': str(message_metadata.get('timestamp', '')),
        }
        
        # Add extraction metadata if available
        if extractions:
            extraction_meta = extractions.get('extraction_metadata', {})
            chroma_metadata.update({
                'urls_found': extraction_meta.get('urls_found', 0),
                'has_link_summaries': bool(extractions.get('link_summaries_combined'))
            })
        
        # Store in ChromaDB (embeddings generated automatically)
        collection.add(
            documents=[document_content],
            metadatas=[chroma_metadata],
            ids=[f"msg_{message_id}"]
        )
        
        logger.info(f"Stored message {message_id} in ChromaDB")
        return True
        
    except Exception as e:
        logger.error(f"Failed to store message {message_id}: {e}")
        return False


def get_server_indexing_status(server_id: int) -> Dict[str, Any]:
    """Get comprehensive indexing status for a server.
    
    Args:
        server_id: Discord server/guild ID
        
    Returns:
        Dictionary with indexing status information
        
    Note:
        Never raises exceptions - returns safe defaults with error info
    """
    try:
        # Import here to avoid circular imports
        from .resumption import get_resumption_info
        
        logger.debug(f"Getting indexing status for server {server_id}")
        resumption_info = get_resumption_info(server_id)
        
        # Determine status based on resumption info
        if resumption_info.message_count == 0:
            status = "empty"
        elif resumption_info.needs_full_processing:
            status = "needs_full_processing"
        elif resumption_info.resumption_recommended:
            status = "can_resume"
        else:
            status = "up_to_date"
        
        result = {
            "server_id": server_id,
            "message_count": resumption_info.message_count,
            "last_indexed_timestamp": resumption_info.last_indexed_timestamp,
            "needs_full_processing": resumption_info.needs_full_processing,
            "resumption_recommended": resumption_info.resumption_recommended,
            "status": status,
            "error": None
        }
        
        logger.debug(f"Server {server_id} status: {status}, {resumption_info.message_count} messages")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get indexing status for server {server_id}: {e.__class__.__name__}: {e}")
        return {
            "server_id": server_id,
            "message_count": 0,
            "last_indexed_timestamp": None,
            "needs_full_processing": True,
            "resumption_recommended": False,
            "status": "error",
            "error": f"{e.__class__.__name__}: {str(e)}"
        }
