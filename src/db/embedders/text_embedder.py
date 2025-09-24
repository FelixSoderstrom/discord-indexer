"""Custom text embedding module for Discord-Indexer.

Provides BGE-large-en-v1.5 embedding functionality through sentence-transformers
with GPU optimization for ChromaDB integration.
"""

import asyncio
import logging
import torch
from typing import List, Union, Optional, Dict
from sentence_transformers import SentenceTransformer
from chromadb.api.types import EmbeddingFunction, Embeddings, Documents
from src.exceptions.message_processing import EmbeddingError
import threading

logger = logging.getLogger(__name__)

# Global singleton instances for embedding models
_embedder_instances: Dict[str, 'BGETextEmbedder'] = {}
_embedder_lock = threading.Lock()


class BGETextEmbedder(EmbeddingFunction[Documents]):
    """BGE-large-en-v1.5 embedding function for ChromaDB.
    
    Implements ChromaDB's EmbeddingFunction interface using the BGE-large-en-v1.5
    model via sentence-transformers with GPU acceleration.
    
    This class implements a singleton pattern to ensure the large embedding model
    is loaded only once and reused across all instances.
    """
    
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5", device: Optional[str] = None):
        """Initialize BGE text embedder.
        
        Args:
            model_name: Hugging Face model identifier
            device: Device to run model on (cuda/cpu). Auto-detects if None.
        """
        self.model_name = model_name
        
        # Auto-detect device if not specified, prioritize GPU
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.debug(f"CUDA available, using GPU for {model_name}")
            else:
                logger.error(f"CUDA not available but required for {model_name}")
                raise EmbeddingError("BGE-large-en-v1.5 requires GPU but CUDA is not available")
        else:
            self.device = device
            
        self._model: Optional[SentenceTransformer] = None
        self._model_loaded = False
        self._load_lock = threading.Lock()
        
    def _load_model(self) -> SentenceTransformer:
        """Thread-safe lazy loading of the sentence transformer model.
        
        Returns:
            Loaded SentenceTransformer model
            
        Raises:
            EmbeddingError: If model loading fails
        """
        if self._model is None:
            with self._load_lock:
                # Double-check locking pattern
                if self._model is None:
                    try:
                        logger.info(f"Loading {self.model_name} on {self.device} (singleton instance)")
                        self._model = SentenceTransformer(
                            self.model_name,
                            device=self.device
                        )
                        self._model_loaded = True
                        logger.info(f"Successfully loaded {self.model_name} (singleton instance)")
                    except Exception as e:
                        logger.error(f"Failed to load model {self.model_name}: {e}")
                        raise EmbeddingError(f"Could not load embedding model: {e}")
                
        return self._model
    
    async def _load_model_async(self) -> None:
        """Load embedding model asynchronously to prevent event loop blocking.
        
        Uses thread-safe loading with double-check locking pattern.
        
        Raises:
            EmbeddingError: If model loading fails
        """
        if self._model is None:
            # Use thread-safe async loading
            await asyncio.to_thread(self._load_model)
    
    async def get_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings asynchronously.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors as lists of floats
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not texts:
            return []
            
        if self._model is None:
            await self._load_model_async()
        
        try:
            # Generate embeddings with normalization for cosine similarity
            embeddings = await asyncio.to_thread(
                self._model.encode,
                texts,
                normalize_embeddings=True,
                convert_to_tensor=False,
                show_progress_bar=False
            )
            
            # Convert to list format
            if embeddings.ndim == 1:
                # Single document case
                return [embeddings.tolist()]
            else:
                # Multiple documents case
                return embeddings.tolist()
                
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise EmbeddingError(f"Embedding generation failed: {str(e)}")
    
    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for input documents.
        
        Args:
            input: List of text documents to embed
            
        Returns:
            List of embedding vectors
            
        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not input:
            return []
            
        try:
            model = self._load_model()
            
            # Generate embeddings with normalization for cosine similarity
            embeddings = model.encode(
                input,
                normalize_embeddings=True,
                convert_to_tensor=False,
                show_progress_bar=False
            )
            
            # Convert to list format expected by ChromaDB
            if embeddings.ndim == 1:
                # Single document case
                return [embeddings.tolist()]
            else:
                # Multiple documents case
                return embeddings.tolist()
                
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise EmbeddingError(f"Embedding generation failed: {e}")


def get_text_embedder(model_name: str = "BAAI/bge-large-en-v1.5") -> BGETextEmbedder:
    """Get a singleton text embedder instance.
    
    This function implements the singleton pattern to ensure that only one
    instance of each embedding model is created and reused across the application.
    This prevents the expensive model loading process from happening multiple times.
    
    Args:
        model_name: Model identifier for embedding model
        
    Returns:
        BGETextEmbedder singleton instance
        
    Raises:
        EmbeddingError: If embedder creation fails
    """
    global _embedder_instances, _embedder_lock
    
    # Thread-safe singleton access
    with _embedder_lock:
        if model_name not in _embedder_instances:
            try:
                logger.info(f"Creating singleton embedder instance for {model_name}")
                _embedder_instances[model_name] = BGETextEmbedder(model_name=model_name)
            except Exception as e:
                logger.error(f"Failed to create text embedder: {e}")
                raise EmbeddingError(f"Could not create embedder: {e}")
        else:
            logger.debug(f"Reusing existing singleton embedder instance for {model_name}")
            
        return _embedder_instances[model_name]


async def preload_embedder(model_name: str = "BAAI/bge-large-en-v1.5") -> BGETextEmbedder:
    """Preload an embedding model asynchronously during startup.
    
    This function should be called during application startup to load the
    embedding model asynchronously, preventing blocking during runtime.
    
    Args:
        model_name: Model identifier for embedding model
        
    Returns:
        Preloaded BGETextEmbedder instance
        
    Raises:
        EmbeddingError: If embedder preloading fails
    """
    try:
        logger.info(f"Preloading embedding model: {model_name}")
        embedder = get_text_embedder(model_name)
        await embedder._load_model_async()
        logger.info(f"Successfully preloaded embedding model: {model_name}")
        return embedder
    except Exception as e:
        logger.error(f"Failed to preload embedding model {model_name}: {e}")
        raise EmbeddingError(f"Could not preload embedding model: {e}")


def clear_embedder_cache() -> None:
    """Clear all cached embedder instances.
    
    This function can be used for testing or to force reload of models.
    Use with caution in production as it will cause models to be reloaded.
    """
    global _embedder_instances
    with _embedder_lock:
        logger.info("Clearing embedder cache")
        _embedder_instances.clear()


def get_loaded_models() -> List[str]:
    """Get list of currently loaded embedding models.
    
    Returns:
        List of model names that are currently loaded in memory
    """
    global _embedder_instances
    with _embedder_lock:
        return [
            model_name for model_name, embedder in _embedder_instances.items()
            if embedder._model_loaded
        ]


def get_supported_models() -> List[str]:
    """Get list of supported embedding models.
    
    Returns:
        List of supported model names
    """
    return [
        "BAAI/bge-large-en-v1.5",
        "BAAI/bge-base-en-v1.5", 
        "BAAI/bge-small-en-v1.5",
        "sentence-transformers/all-MiniLM-L6-v2",
        "sentence-transformers/all-mpnet-base-v2"
    ]