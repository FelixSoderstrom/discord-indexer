"""Message processing resumption utilities.

Provides functionality to determine where message indexing should resume
from by checking the last indexed message timestamp in ChromaDB collections.
"""

import logging
from datetime import datetime
from typing import Optional, NamedTuple
from pathlib import Path
from src.db import get_db
from chromadb.errors import ChromaError, NotFoundError

logger = logging.getLogger(__name__)


class ResumptionInfo(NamedTuple):
    """Information about where to resume message processing for a server.
    
    Attributes:
        server_id: Discord server/guild ID
        last_indexed_timestamp: ISO timestamp of most recent indexed message, None if no messages
        message_count: Total number of messages currently indexed
        needs_full_processing: True if full historical processing is needed
        resumption_recommended: True if resumption from timestamp is recommended
    """
    server_id: int
    last_indexed_timestamp: Optional[str]
    message_count: int
    needs_full_processing: bool
    resumption_recommended: bool


def get_last_indexed_timestamp(server_id: int) -> Optional[str]:
    """Get the timestamp of the most recently indexed message for a server.
    
    Args:
        server_id: Discord server/guild ID
        
    Returns:
        ISO timestamp string of most recent message, None if no messages indexed
        
    Raises:
        ChromaError: If ChromaDB query fails
        OSError: If database cannot be accessed
    """
    try:
        # Get ChromaDB client for this server
        db_client = get_db(server_id)
        
        # Get messages collection
        collection_name = "messages"
        try:
            collection = db_client.get_collection(collection_name)
        except (NotFoundError, ValueError, RuntimeError, ChromaError):
            # Collection doesn't exist, no messages indexed
            logger.info(f"No messages collection found for server {server_id}")
            return None
        
        # Check if collection has any messages
        message_count = collection.count()
        if message_count == 0:
            logger.info(f"Messages collection empty for server {server_id}")
            return None
        
        # Get all messages to find the most recent timestamp
        # Note: ChromaDB doesn't have built-in sorting, so we need to get all and sort
        results = collection.get(include=["metadatas"])
        
        if not results["metadatas"]:
            logger.warning(f"No metadata found in messages collection for server {server_id}")
            return None
        
        # Find the most recent timestamp from all message metadata
        latest_timestamp = None
        for metadata in results["metadatas"]:
            if metadata and "timestamp" in metadata:
                timestamp_str = metadata["timestamp"]
                if not latest_timestamp or timestamp_str > latest_timestamp:
                    latest_timestamp = timestamp_str
        
        if latest_timestamp:
            logger.info(f"Server {server_id}: Last indexed message at {latest_timestamp}")
        else:
            logger.warning(f"Server {server_id}: No valid timestamps found in {message_count} messages")
        
        return latest_timestamp
        
    except (ChromaError, ValueError, TypeError, ConnectionError, OSError, MemoryError) as e:
        logger.error(f"Failed to get last indexed timestamp for server {server_id}: {e}")
        raise


def get_resumption_info(server_id: int) -> ResumptionInfo:
    """Get comprehensive resumption information for a server.
    
    Args:
        server_id: Discord server/guild ID
        
    Returns:
        ResumptionInfo with processing recommendations
        
    Note:
        Never raises exceptions - returns safe defaults on errors
    """
    try:
        # Check if database directory exists first
        db_path = Path(__file__).parent.parent / "db" / "databases" / str(server_id)
        if not db_path.exists():
            logger.info(f"Server {server_id}: Database directory does not exist - full processing needed")
            return ResumptionInfo(
                server_id=server_id,
                last_indexed_timestamp=None,
                message_count=0,
                needs_full_processing=True,
                resumption_recommended=False
            )
        
        # Get ChromaDB client for this server
        db_client = get_db(server_id)
        
        # Check if messages collection exists
        collection_name = "messages"
        try:
            collection = db_client.get_collection(collection_name)
            message_count = collection.count()
        except (NotFoundError, ValueError, RuntimeError, ChromaError) as e:
            # Collection doesn't exist or is corrupted, needs full processing
            logger.info(f"Server {server_id}: No messages collection ({e.__class__.__name__}) - full processing needed")
            return ResumptionInfo(
                server_id=server_id,
                last_indexed_timestamp=None,
                message_count=0,
                needs_full_processing=True,
                resumption_recommended=False
            )
        
        # Empty collection, needs full processing
        if message_count == 0:
            logger.info(f"Server {server_id}: Empty collection - full processing needed")
            return ResumptionInfo(
                server_id=server_id,
                last_indexed_timestamp=None,
                message_count=0,
                needs_full_processing=True,
                resumption_recommended=False
            )
        
        # Get last indexed timestamp
        try:
            last_timestamp = get_last_indexed_timestamp(server_id)
        except (ChromaError, ValueError, TypeError, ConnectionError, OSError, MemoryError) as e:
            logger.warning(f"Server {server_id}: Failed to get last timestamp ({e.__class__.__name__}), defaulting to full processing")
            return ResumptionInfo(
                server_id=server_id,
                last_indexed_timestamp=None,
                message_count=message_count,
                needs_full_processing=True,
                resumption_recommended=False
            )
        
        # Determine processing recommendation
        needs_full = last_timestamp is None
        resumption_recommended = last_timestamp is not None
        
        # Validate timestamp if present
        if last_timestamp:
            try:
                parse_discord_timestamp(last_timestamp)
            except ValueError as e:
                logger.warning(f"Server {server_id}: Invalid timestamp '{last_timestamp}' ({e}), defaulting to full processing")
                return ResumptionInfo(
                    server_id=server_id,
                    last_indexed_timestamp=None,
                    message_count=message_count,
                    needs_full_processing=True,
                    resumption_recommended=False
                )
        
        logger.info(f"Server {server_id}: {message_count} messages indexed, "
                   f"last: {last_timestamp or 'None'}, "
                   f"resumption: {resumption_recommended}")
        
        return ResumptionInfo(
            server_id=server_id,
            last_indexed_timestamp=last_timestamp,
            message_count=message_count,
            needs_full_processing=needs_full,
            resumption_recommended=resumption_recommended
        )
        
    except (OSError, PermissionError, ChromaError, RuntimeError, ValueError, TypeError) as e:
        logger.error(f"Failed to get resumption info for server {server_id}: {e.__class__.__name__}: {e}")
        # Default to full processing on any error
        return ResumptionInfo(
            server_id=server_id,
            last_indexed_timestamp=None,
            message_count=0,
            needs_full_processing=True,
            resumption_recommended=False
        )


def parse_discord_timestamp(timestamp_str: str) -> datetime:
    """Parse Discord timestamp string to datetime object.
    
    Args:
        timestamp_str: ISO timestamp string from Discord message
        
    Returns:
        datetime object (timezone-aware)
        
    Raises:
        ValueError: If timestamp string is invalid
    """
    try:
        # Discord timestamps are in ISO format with timezone
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError as e:
        logger.error(f"Failed to parse timestamp '{timestamp_str}': {e}")
        raise