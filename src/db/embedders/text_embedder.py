"""Custom text embedding module for Discord-Indexer.

Provides BGE-large-en-v1.5 embedding functionality through sentence-transformers
with GPU optimization for ChromaDB integration.
"""

import logging
import torch
from typing import List, Union, Optional
from sentence_transformers import SentenceTransformer
from chromadb.api.types import EmbeddingFunction, Embeddings, Documents

logger = logging.getLogger(__name__)


class BGETextEmbedder(EmbeddingFunction[Documents]):
    """BGE-large-en-v1.5 embedding function for ChromaDB.
    
    Implements ChromaDB's EmbeddingFunction interface using the BGE-large-en-v1.5
    model via sentence-transformers with GPU acceleration.
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
                logger.info(f"CUDA available, using GPU for {model_name}")
            else:
                logger.error(f"CUDA not available but required for {model_name}")
                raise RuntimeError("BGE-large-en-v1.5 requires GPU but CUDA is not available")
        else:
            self.device = device
            
        self._model: Optional[SentenceTransformer] = None
        
    def _load_model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model.
        
        Returns:
            Loaded SentenceTransformer model
            
        Raises:
            RuntimeError: If model loading fails
        """
        if self._model is None:
            try:
                logger.info(f"Loading {self.model_name} on {self.device}")
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device
                )
                logger.info(f"Successfully loaded {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {e}")
                raise RuntimeError(f"Could not load embedding model: {e}")
                
        return self._model
    
    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for input documents.
        
        Args:
            input: List of text documents to embed
            
        Returns:
            List of embedding vectors
            
        Raises:
            RuntimeError: If embedding generation fails
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
            raise RuntimeError(f"Embedding generation failed: {e}")


def get_text_embedder(model_name: str = "BAAI/bge-large-en-v1.5") -> BGETextEmbedder:
    """Get a text embedder instance.
    
    Args:
        model_name: Model identifier for embedding model
        
    Returns:
        BGETextEmbedder instance
        
    Raises:
        RuntimeError: If embedder creation fails
    """
    try:
        return BGETextEmbedder(model_name=model_name)
    except Exception as e:
        logger.error(f"Failed to create text embedder: {e}")
        raise RuntimeError(f"Could not create embedder: {e}")


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