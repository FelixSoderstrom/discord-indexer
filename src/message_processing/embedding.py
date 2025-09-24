"""Image processing functionality for Discord message attachments.

Handles generation of text descriptions for image attachments using vision models.
Text embeddings are handled automatically by ChromaDB during storage.
"""

import logging
from typing import Dict, Any, List, Optional

from src.message_processing.image_processor import process_message_images
from src.exceptions.message_processing import MessageProcessingError
from src.config.settings import settings

logger = logging.getLogger(__name__)


def process_message_embeddings(message_data: Dict[str, Any], extractions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process image descriptions for message attachments.
    
    Generates text descriptions for image attachments using vision models.
    Text content is processed automatically by ChromaDB during document storage.
    
    Args:
        message_data: Complete message data dictionary
        extractions: Extraction results (unused, kept for compatibility)
        
    Returns:
        Dictionary containing image processing results
    """
    embedding_results = {
        'image_descriptions': '',
        'embedding_metadata': {
            'images_processed': 0,
            'processing_model': settings.VISION_MODEL_NAME,
            'processing_successful': False
        }
    }
    
    # Process image attachments if present
    attachments = message_data.get('attachments', [])
    if attachments:
        try:
            logger.info(f"Processing {len(attachments)} image attachments")
            
            # Generate descriptions for all images
            image_descriptions = process_message_images(attachments)
            
            embedding_results['image_descriptions'] = image_descriptions
            embedding_results['embedding_metadata']['images_processed'] = len(attachments)
            embedding_results['embedding_metadata']['processing_successful'] = True
            
            logger.info(f"Successfully generated descriptions for {len(attachments)} images")
            
        except MessageProcessingError as e:
            logger.warning(f"Image processing failed: {e}")
            # Re-raise to trigger message-level error handling
            raise
        except Exception as e:
            logger.error(f"Unexpected error during image processing: {e}")
            raise MessageProcessingError(f"Unexpected image processing error: {str(e)}")
    
    return embedding_results


async def process_message_embeddings_async(message_data: Dict[str, Any], extractions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process image descriptions and embeddings for message attachments asynchronously.
    
    Generates text descriptions for image attachments using vision models and
    processes text embeddings using async embedding functions.
    
    Args:
        message_data: Complete message data dictionary
        extractions: Extraction results (unused, kept for compatibility)
        
    Returns:
        Dictionary containing image and embedding processing results
    """
    embedding_results = {
        'image_descriptions': '',
        'embedding_metadata': {
            'images_processed': 0,
            'processing_model': settings.VISION_MODEL_NAME,
            'processing_successful': False
        }
    }
    
    # Process image attachments if present
    attachments = message_data.get('attachments', [])
    if attachments:
        try:
            logger.info(f"Processing {len(attachments)} image attachments")
            
            # Generate descriptions for all images (now async)
            image_descriptions = await process_message_images(attachments)
            
            embedding_results['image_descriptions'] = image_descriptions
            embedding_results['embedding_metadata']['images_processed'] = len(attachments)
            embedding_results['embedding_metadata']['processing_successful'] = True
            
            logger.info(f"Successfully generated descriptions for {len(attachments)} images")
            
        except MessageProcessingError as e:
            logger.warning(f"Image processing failed: {e}")
            # Re-raise to trigger message-level error handling
            raise
        except Exception as e:
            logger.error(f"Unexpected error during image processing: {e}")
            raise MessageProcessingError(f"Unexpected image processing error: {str(e)}")
    
    return embedding_results


async def store_message_embeddings_async(message_data: dict, collection_name: str = "messages") -> None:
    """Store message embeddings asynchronously."""
    try:
        from src.db.embedders.text_embedder import BGETextEmbedder
        
        embedder = BGETextEmbedder()
        
        # Use async embedding generation
        text_content = message_data.get('content', '')
        if text_content:
            embeddings = await embedder.get_embeddings_async([text_content])
            # Store to ChromaDB (existing logic)
            # Note: Storage logic would be handled by database-manager agent
            logger.info(f"Generated embeddings for message content: {len(embeddings)} vectors")
            
    except Exception as e:
        logger.error(f"Failed to store message embeddings: {e}")
        raise

