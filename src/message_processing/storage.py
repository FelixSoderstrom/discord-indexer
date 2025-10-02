"""ChromaDB storage for processed Discord messages.

Stores message content with metadata in ChromaDB collections. 
ChromaDB automatically handles text embeddings for semantic search.
"""

import logging
from typing import Dict, Any, Optional
from chromadb.api.types import EmbeddingFunction

from src.db import get_db, get_server_embedding_model
from chromadb.errors import ChromaError, NotFoundError
from src.exceptions.message_processing import DatabaseConnectionError
from src.db.embedders.text_embedder import get_text_embedder


logger = logging.getLogger(__name__)


def get_collection(server_id: int, collection_name: str = "messages", custom_embedder: Optional[EmbeddingFunction] = None):
    """Get or create a ChromaDB collection with optimal embedder reuse.
    
    This function uses singleton embedders to prevent multiple model loading
    for the same embedding model. Each unique model is loaded once and reused.
    
    Args:
        server_id: Discord server/guild ID
        collection_name: Name of the collection to get/create
        custom_embedder: Optional custom embedding function
        
    Returns:
        ChromaDB collection instance
        
    Raises:
        ChromaError: If collection operations fail
        RuntimeError: If custom embedder initialization fails
    """
    try:
        # Get ChromaDB client for this server
        server_embedding_model = get_server_embedding_model(server_id)
        db_client = get_db(server_id, server_embedding_model)
        
        # Determine which embedder to use
        embedder = custom_embedder
        if embedder is None and server_embedding_model:
            try:
                # Use singleton embedder to prevent multiple model loading
                embedder = get_text_embedder(server_embedding_model)
                logger.debug(f"Using singleton embedder {server_embedding_model} for server {server_id}")
            except RuntimeError as e:
                logger.warning(f"Failed to load custom embedder {server_embedding_model}: {e}")
                logger.info(f"Falling back to default embedder for server {server_id}")
                embedder = None
        
        # Get or create collection with appropriate embedder
        try:
            if embedder is not None:
                collection = db_client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=embedder
                )
            else:
                collection = db_client.get_or_create_collection(name=collection_name)
                
            logger.debug(f"Got collection '{collection_name}' for server {server_id}")
            return collection
            
        except (NotFoundError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to get/create collection {collection_name} for server {server_id}: {e}")
            raise
            
    except Exception as e:
        logger.error(f"Failed to get collection for server {server_id}: {e}")
        raise


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
    embeddings = processed_data.get('embeddings', {})
    
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
        # Get collection with configured embedding model
        collection = get_collection(server_id, "messages")
        
        # Prepare document content with standardized format
        message_text = message_metadata.get('content', '').strip()
        link_summaries = extractions.get('link_summaries_combined', '').strip() if extractions else ''
        image_descriptions = embeddings.get('image_descriptions', '').strip() if embeddings else ''

        # Always start with "User said:" prefix
        if message_text:
            document_content = f"User said: {message_text}"
        else:
            document_content = "User said: [NULL]"

        # Add image descriptions if available
        if image_descriptions:
            document_content += f"\nAttached image contains: {image_descriptions}"

        # Add link summaries if available
        if link_summaries:
            document_content += f"\nAttached link contains: {link_summaries}"
        
        # Skip empty messages
        if not document_content.strip():
            logger.info(f"Skipping empty message {message_id}")
            return True
        
        # Prepare metadata for ChromaDB
        chroma_metadata = {
            'message_id': str(message_id),
            'author_id': str(author_metadata.get('author_id', '')),
            'author_name': str(author_metadata.get('author_name', '')),
            'author_display_name': str(author_metadata.get('author_display_name', '')),
            'author_global_name': str(author_metadata.get('author_global_name', '')),
            'author_nick': str(author_metadata.get('author_nick', '')),
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
        
        # Add image processing metadata if available
        if embeddings:
            embedding_meta = embeddings.get('embedding_metadata', {})
            chroma_metadata.update({
                'images_processed': embedding_meta.get('images_processed', 0),
                'has_image_descriptions': bool(embeddings.get('image_descriptions')),
                'image_processing_model': embedding_meta.get('processing_model', '')
            })
        
        # Store in ChromaDB (embeddings generated automatically)
        collection.add(
            documents=[document_content],
            metadatas=[chroma_metadata],
            ids=[f"msg_{message_id}"]
        )
        
        logger.info(f"Stored message {message_id} in ChromaDB")
        return True
        
    except (ChromaError, ValueError, TypeError, ConnectionError, OSError, MemoryError) as e:
        logger.error(f"Failed to store message {message_id}: {e}")
        raise DatabaseConnectionError(f"Failed to store message {message_id}: {e}")


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
        from src.message_processing.resumption import get_resumption_info
        
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
        
    except (ImportError, AttributeError, KeyError, ValueError, TypeError, OSError) as e:
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
