import logging

logger = logging.getLogger(__name__)

class MessageProcessingError(Exception):
    """
    This exception is raised when a message fails to be processed 
    due to an error in the message processing pipeline.
    
    Triggering this exception automatically stops a single message from being processed and continues with the next one.
    """
    def __init__(self):
        logger.warning("Message processing failed.")