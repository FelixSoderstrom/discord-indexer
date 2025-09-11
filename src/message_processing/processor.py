"""Main message processing pipeline coordinator.

Provides the MessagePipeline class that orchestrates the complete
message processing workflow from raw Discord messages through
embedding, extraction, metadata preparation, and storage.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from collections import defaultdict

from src.message_processing.embedding import process_message_embeddings
from src.message_processing.extraction import process_message_extractions
from src.message_processing.metadata import process_message_metadata
from src.message_processing.storage import store_complete_message
from src.exceptions.message_processing import MessageProcessingError


logger = logging.getLogger(__name__)


class MessagePipeline:
    """Main message processing pipeline class.
    
    Coordinates the complete processing workflow for Discord messages,
    including content analysis, embedding generation, metadata preparation,
    and database storage.
    """
    
    def __init__(self, completion_event: Optional[asyncio.Event] = None) -> None:
        """Initialize the message processing pipeline.
        
        Args:
            completion_event: Event to signal when batch processing is complete
        """
        logger.info("Initializing MessagePipeline")
        
        # Processing statistics
        self.messages_processed = 0
        self.messages_failed = 0
        
        # Async coordination
        self.completion_event = completion_event
        
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
    
    async def _route_message_processing(self, message_data: Dict[str, Any], content_analysis: Dict[str, bool]) -> Dict[str, Any]:
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
        
        # Process extractions if there are URLs or mentions
        extractions = {}
        if content_analysis['has_urls'] or content_analysis['has_mentions']:
            logger.info("Processing message extractions")
            extractions = await process_message_extractions(message_data)
            processed_data['extractions'] = extractions
        
        # Process embeddings if there's text or images
        if content_analysis['has_text'] or content_analysis['has_images']:
            logger.info("Processing message embeddings")
            processed_data['embeddings'] = process_message_embeddings(message_data, extractions)
        
        processed_data['processing_status'] = 'completed'
        return processed_data
    
    def _group_messages_by_server(self, messages: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """Group messages by server ID for separate processing.
        
        Args:
            messages: List of message data dictionaries
            
        Returns:
            Dictionary mapping server IDs to lists of messages
        """
        grouped_messages = defaultdict(list)
        
        for message in messages:
            guild_data = message.get('guild', {})
            server_id = guild_data.get('id')
            
            if server_id:
                grouped_messages[server_id].append(message)
            else:
                logger.warning(f"Message {message.get('id', 'unknown')} has no server ID - skipping")
        
        return dict(grouped_messages)
    
    def _sort_messages_chronologically(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort messages in chronological order by timestamp.
        
        Args:
            messages: List of message data dictionaries
            
        Returns:
            List of messages sorted by timestamp (oldest first)
        """
        return sorted(messages, key=lambda msg: msg.get('timestamp', ''))
    
    async def process_messages(self, messages: List[Dict[str, Any]]) -> bool:
        """Process a list of Discord messages through the complete pipeline.
        
        Main entry point for message processing. Groups messages by server ID,
        then processes each server separately with chronological sorting.
        
        Args:
            messages: List of raw message data dictionaries from Discord
            
        Returns:
            True if all messages processed successfully,
            False if any message failed
        """
        if not messages:
            logger.info("No messages to process")
            if self.completion_event:
                self.completion_event.set()
            return True
            
        logger.info(f"Processing batch of {len(messages)} messages")
    
        # Group messages by server ID to process each server separately
        grouped_by_server = self._group_messages_by_server(messages)
        logger.info(f"Messages grouped by server: {len(grouped_by_server)} servers")
        
        # Process each server separately
        for server_id, server_messages in grouped_by_server.items():
            logger.info(f"Processing {len(server_messages)} messages from server {server_id}")
            
            # Sort messages chronologically within this server
            sorted_messages = self._sort_messages_chronologically(server_messages)
            logger.info(f"Messages sorted chronologically for server {server_id}")
            
            # Process each message sequentially within this server
            for i, message_data in enumerate(sorted_messages, 1):
                message_id = message_data.get('id', 'unknown')
                logger.info(f"Processing server {server_id} message {i}/{len(sorted_messages)} - ID: {message_id}")
                
                try:
                    # Analyze message content to determine processing requirements
                    content_analysis = self._check_message_content(message_data)
                    
                    # Skip empty messages
                    if content_analysis['is_empty']:
                        logger.info("Skipping empty message")
                        continue
                    
                    # Route message through appropriate processing steps
                    processed_data = await self._route_message_processing(message_data, content_analysis)
                    
                    # Store processed data to database using server-specific client
                    logger.info("Storing processed message to database")
                    storage_success = store_complete_message(processed_data)
                    
                    if storage_success:
                        self.messages_processed += 1
                        logger.debug(f"Message {message_id} processed successfully. Total processed: {self.messages_processed}")
                    else:
                        self.messages_failed += 1
                        logger.error(f"Failed to store message {message_id} from server {server_id}")
                        continue
                
                except MessageProcessingError:
                    logger.warning(f"Message failed to process, skipping message {message_id}")
                    self.messages_failed += 1
                    continue
            
            logger.info(f"Server {server_id} processing completed successfully. Processed {len(sorted_messages)} messages")
        
        logger.info(f"All servers processed successfully. Total processed: {len(messages)} messages")
        
        # Signal completion if event is available
        if self.completion_event:
            self.completion_event.set()
        
        return True
                

    
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
