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


class CleanupError(Exception):
    """
    Base exception for cleanup operation failures.

    This exception is raised when cleanup operations encounter errors
    that prevent proper resource cleanup during bot shutdown.
    """
    def __init__(self, message: str = "Cleanup operation failed"):
        super().__init__(message)
        logger.warning(f"Cleanup operation failed: {message}")


class DiscordCleanupError(CleanupError):
    """
    This exception is raised when Discord resource cleanup fails
    due to voice channel cleanup, connection errors, or permission issues.

    Triggering this exception logs the error but allows other cleanup operations to continue.
    """
    def __init__(self, message: str = "Discord cleanup failed"):
        super().__init__(message)
        logger.warning(f"Discord cleanup failed: {message}")


class LLMCleanupError(CleanupError):
    """
    This exception is raised when LLM resource cleanup fails
    due to Ollama connection errors or model unloading failures.

    Triggering this exception logs the error but allows other cleanup operations to continue.
    """
    def __init__(self, message: str = "LLM cleanup failed"):
        super().__init__(message)
        logger.warning(f"LLM cleanup failed: {message}")


class DatabaseCleanupError(CleanupError):
    """
    This exception is raised when database cleanup fails
    due to ChromaDB or SQLite connection errors.

    Triggering this exception logs the error but allows other cleanup operations to continue.
    """
    def __init__(self, message: str = "Database cleanup failed"):
        super().__init__(message)
        logger.warning(f"Database cleanup failed: {message}")