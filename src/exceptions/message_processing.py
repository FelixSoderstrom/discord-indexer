import logging

logger = logging.getLogger(__name__)

class MessageProcessingError(Exception):
    """
    This exception is raised when a message fails to be processed
    due to an error in the message processing pipeline.

    Triggering this exception automatically stops a single message from being processed and continues with the next one.
    """
    def __init__(self, message: str = "Message processing failed"):
        super().__init__(message)
        logger.warning(f"Message processing failed: {message}")


class DatabaseConnectionError(Exception):
    """
    This exception is raised when database operations fail
    due to ChromaDB connection or operation errors.

    Triggering this exception allows configuration-based handling of database failures.
    """
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)
        logger.warning(f"Database operation failed: {message}")


class LLMProcessingError(Exception):
    """
    This exception is raised when LLM operations fail
    due to Ollama connection or model processing errors.

    Triggering this exception allows configuration-based handling of LLM failures.
    """
    def __init__(self, message: str = "LLM processing failed"):
        super().__init__(message)
        logger.warning(f"LLM processing failed: {message}")