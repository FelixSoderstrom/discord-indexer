"""Text embedding module for Discord-Indexer.

Provides custom embedding functionality for ChromaDB with support for
various embedding models including BGE and sentence-transformers.
"""

from src.db.embedders.text_embedder import (
    BGETextEmbedder, 
    get_text_embedder, 
    get_supported_models,
    preload_embedder,
    clear_embedder_cache,
    get_loaded_models
)

__all__ = [
    "BGETextEmbedder", 
    "get_text_embedder", 
    "get_supported_models",
    "preload_embedder",
    "clear_embedder_cache", 
    "get_loaded_models"
]