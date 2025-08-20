"""Main message processing pipeline coordinator.

Provides the MessagePipeline class that orchestrates the complete
message processing workflow from raw Discord messages through
embedding, extraction, metadata preparation, and storage.
"""

import logging
from typing import Dict, Any, Optional

from .embedding import process_message_embeddings
from .extraction import process_message_extractions
from .metadata import process_message_metadata
from .storage import store_complete_message


logger = logging.getLogger(__name__)


class MessagePipeline:
    """Main message processing pipeline class.
    
    Coordinates the complete processing workflow for Discord messages,
    including content analysis, embedding generation, metadata preparation,
    and database storage.
    """
    
    def __init__(self) -> None:
        """Initialize the message processing pipeline."""
        logger.info("Initializing MessagePipeline")
        
        # Processing statistics
        self.messages_processed = 0
        self.messages_failed = 0
        
        logger.info("MessagePipeline initialized successfully")
    
    def _check_message_content(self, message_data: Dict[str, Any]) -> Dict[str, bool]:
        """Analyze message content to determine processing requirements.
        
        Args:
            message_data: Raw message data from Discord
            
        Returns:
            Dictionary indicating what content types are present
        """
        content = message_data.get('content', '')
        attachments = message_data.get('attachments', [])
        
        content_analysis = {
            'has_text': bool(content.strip()),
            'has_images': len(attachments) > 0,
            'has_urls': 'http' in content.lower(),
            'has_mentions': '@' in content or '#' in content,
            'is_empty': not content.strip() and len(attachments) == 0
        }
        
        logger.debug(f"Content analysis: {content_analysis}")
        return content_analysis
    
    def _route_message_processing(self, message_data: Dict[str, Any], content_analysis: Dict[str, bool]) -> Dict[str, Any]:
        """Route message through appropriate processing steps based on content.
        
        Args:
            message_data: Raw message data from Discord
            content_analysis: Analysis of message content types
            
        Returns:
            Dictionary containing all processed data
        """
        logger.info("Routing message through processing pipeline")
        
        processed_data = {
            'metadata': {},
            'embeddings': {},
            'extractions': {},
            'processing_status': 'in_progress'
        }
        
        # Always process metadata
        logger.info("Processing message metadata")
        processed_data['metadata'] = process_message_metadata(message_data)
        
        # Process embeddings if there's text or images
        if content_analysis['has_text'] or content_analysis['has_images']:
            logger.info("Processing message embeddings")
            processed_data['embeddings'] = process_message_embeddings(message_data)
        
        # Process extractions if there are URLs or mentions
        if content_analysis['has_urls'] or content_analysis['has_mentions']:
            logger.info("Processing message extractions")
            processed_data['extractions'] = process_message_extractions(message_data)
        
        processed_data['processing_status'] = 'completed'
        return processed_data
    
    def process_message(self, message_data: Dict[str, Any]) -> bool:
        """Process a single Discord message through the complete pipeline.
        
        Main entry point for message processing. Analyzes content,
        routes through appropriate processing steps, and stores results.
        
        Args:
            message_data: Raw message data dictionary from Discord
            
        Returns:
            True if processing successful and ready for next message,
            False if processing failed
        """
        logger.info(f"Processing message ID: {message_data.get('id', 'unknown')}")
        
        try:
            # Analyze message content to determine processing requirements
            content_analysis = self._check_message_content(message_data)
            
            # Skip empty messages
            if content_analysis['is_empty']:
                logger.info("Skipping empty message")
                return True
            
            # Route message through appropriate processing steps
            processed_data = self._route_message_processing(message_data, content_analysis)
            
            # Store processed data to database using context manager
            logger.info("Storing processed message to database")
            storage_success = store_complete_message(processed_data)
            
            if storage_success:
                self.messages_processed += 1
                logger.info(f"Message processing completed successfully. Total processed: {self.messages_processed}")
                return True
            else:
                self.messages_failed += 1
                logger.error("Failed to store processed message")
                return False
                
        except Exception as e:
            self.messages_failed += 1
            logger.error(f"Error processing message: {e}")
            return False
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics.
        
        Returns:
            Dictionary containing processing statistics
        """
        return {
            'messages_processed': self.messages_processed,
            'messages_failed': self.messages_failed,
            'success_rate': self.messages_processed / max(1, self.messages_processed + self.messages_failed)
        }
