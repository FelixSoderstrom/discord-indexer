# BGE Embedder Specialist Agent Instructions

## Key Areas of Focus
- `src/db/embedders/text_embedder.py` - Core BGE embedding implementation with singleton pattern
- `src/db/embedders/__init__.py` - Module exports and preloading functions
- `src/message_processing/storage.py` - Collection management with optimized embedder reuse
- `main.py` - Startup sequence with async BGE model preloading
- `src/setup/server_setup.py` - Server-specific embedding model configuration

## Specific Responsibilities
### BGE Model Lifecycle Management
- BGE-large-en-v1.5 model initialization with GPU/CUDA enforcement
- Thread-safe singleton pattern implementation for memory optimization
- Async model preloading during startup to prevent Discord heartbeat timeouts
- Model loading with double-check locking pattern for thread safety
- SentenceTransformer model management with normalized embeddings

### Embedding Generation Operations
- Synchronous embedding generation via `__call__` method for ChromaDB integration
- Asynchronous embedding generation via `get_embeddings_async` for non-blocking operations
- Batch processing with normalize_embeddings=True for cosine similarity
- GPU-optimized processing with CUDA device selection
- Proper tensor to list conversion for ChromaDB compatibility

### Performance Optimization & Memory Management
- Singleton pattern preventing 17+ redundant model loads
- Global instance caching with `_embedder_instances` dictionary
- Thread-safe access using `_embedder_lock` and `_load_lock`
- Async startup preloading to eliminate runtime blocking
- Memory-efficient model reuse across collection operations

### Integration with ChromaDB & Storage Layer
- ChromaDB EmbeddingFunction[Documents] interface implementation
- Collection creation with custom embedder assignment
- Server-specific embedding model detection and application
- Graceful fallback to default ChromaDB embeddings on failures
- Optimized embedder reuse in `get_collection()` function

### Hardware Requirements & GPU Management
- CUDA availability detection and enforcement for BGE models
- Automatic device selection (cuda/cpu) with GPU prioritization
- GPU memory management for large embedding models (~1.3GB VRAM)
- Hardware compatibility validation during initialization
- Error handling for insufficient GPU resources

## Coordination Boundaries
- **Works WITH storage layer**: Provides embedders for ChromaDB collection creation
- **Works WITH server setup**: Handles embedding model configuration validation
- **Works WITH main startup**: Provides async preloading during bot initialization
- **Does NOT**: Handle message content processing or storage operations
- **Does NOT**: Manage ChromaDB collections or query operations
- **Does NOT**: Handle server configuration UI or database schema

## Implementation Process
1. **Analysis Phase**: Examine BGE model requirements and performance characteristics
2. **Planning Phase**: Design singleton pattern and async loading strategies
3. **Implementation Phase**: Build thread-safe model management and embedding generation
4. **Testing Phase**: Validate GPU operations, singleton behavior, and embedder integration
5. **Optimization Phase**: Tune for RTX 3090 hardware and memory efficiency

## BGE Model Specifications
### Supported Models
- `BAAI/bge-large-en-v1.5` (1024 dimensions, 335M parameters, GPU required)
- `BAAI/bge-base-en-v1.5` (768 dimensions, reduced memory footprint)
- `BAAI/bge-small-en-v1.5` (384 dimensions, lightweight option)
- `sentence-transformers/all-MiniLM-L6-v2` (CPU fallback)
- `sentence-transformers/all-mpnet-base-v2` (balanced performance)

### Hardware Prerequisites
- NVIDIA GPU with CUDA support for BGE models
- Minimum 2GB VRAM (BGE-large requires ~1.3GB)
- CUDA driver version 11.8+ recommended
- RTX 3090 + 16GB RAM optimization target

## Testing Approach
- Create test scripts for singleton pattern validation
- Test async preloading during startup sequence
- Validate GPU/CUDA detection and enforcement
- Test thread-safe concurrent access to embedders
- Verify ChromaDB integration with custom embedding functions
- Performance testing with large message batches (50+ messages)
- Memory usage validation for singleton pattern effectiveness

## Error Handling Patterns
- `EmbeddingError` for BGE model loading failures
- CUDA availability validation with descriptive error messages
- Graceful fallback to default ChromaDB embeddings when custom models fail
- Thread-safe error handling during concurrent model access
- Specific exception catching (no broad Exception handling)

## Key Performance Targets
- Eliminate multiple redundant model loads (17+ → 1 singleton)
- Reduce first message processing latency from ~10s to <1s
- Sub-5-second embedding generation for message batches
- Stable operation on consumer hardware specifications
- Memory efficiency through proper singleton lifecycle management