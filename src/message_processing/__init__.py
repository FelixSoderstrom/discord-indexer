"""Message processing pipeline for Discord message indexing.

This module provides the core message processing pipeline that handles
Discord messages through various stages including embedding, extraction,
metadata preparation, and storage.
"""

from src.message_processing.processor import MessagePipeline

__all__ = ['MessagePipeline']

