# Custom Embedding Models

## Overview

The Discord-Indexer supports custom text embedding models for enhanced semantic search capabilities. This system allows per-server configuration of embedding models, with support for GPU-accelerated models like BGE-large-en-v1.5 while maintaining graceful fallback to default ChromaDB embeddings.

## Architecture

### Core Components

#### 1. Text Embedder Module (`src/db/embedders/text_embedder.py`)
Standalone module providing custom embedding functionality with ChromaDB integration and singleton pattern for optimal memory usage.

**Key Classes:**
- `BGETextEmbedder`: ChromaDB-compatible embedding function for BGE models
- Implements `EmbeddingFunction[Documents]` interface
- GPU-only enforcement with automatic CUDA detection
- Normalized embeddings for cosine similarity
- Thread-safe singleton pattern with model caching

**Performance Features:**
- **Singleton Pattern**: Each model is loaded once and reused across all instances
- **Async Preloading**: Models can be preloaded during startup to prevent runtime blocking
- **Thread Safety**: Multiple threads can safely access the same embedder instance
- **Memory Optimization**: Prevents duplicate model loading (eliminates 17+ redundant loads)

**Supported Models:**
- `BAAI/bge-large-en-v1.5` (1024 dimensions, 335M parameters, GPU required)
- `BAAI/bge-base-en-v1.5` 
- `BAAI/bge-small-en-v1.5`
- `sentence-transformers/all-MiniLM-L6-v2` (lightweight fallback)
- `sentence-transformers/all-mpnet-base-v2`

#### 2. Enhanced Storage Layer (`src/message_processing/storage.py`)
New `get_collection()` function providing centralized collection management with optimized embedder reuse.

**Features:**
- Server-specific embedding model detection via `get_server_embedding_model()`
- Singleton embedder access with automatic reuse  
- Custom embedder initialization with `EmbeddingError` handling
- Graceful fallback to default ChromaDB embeddings on any failure
- Zero-cost embedder reuse across multiple collection calls
- Thread-safe collection access with optimized model loading

#### 3. Server Configuration System (`src/setup/server_setup.py`)
Extended terminal UI for embedding model selection during server setup.

**Configuration Options:**
1. **Global Default**: Uses environment variable `EMBEDDING_MODEL_NAME`
2. **BGE-large-en-v1.5**: High accuracy, GPU required
3. **Lightweight Model**: Faster processing, CPU compatible
4. **Custom Model**: User-specified model name

#### 4. Database Integration (`src/db/setup_db.py`)
Enhanced ChromaDB client management with embedding model isolation.

**Features:**
- Client caching with embedding model keys
- Server embedding model lookup from configuration database
- Backward compatible schema updates

## Configuration

### Environment Variables

```bash
# Global default embedding model
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

### Server-Specific Configuration

Each Discord server can override the global default during setup via interactive terminal UI:

```
🧠 EMBEDDING MODEL CONFIGURATION
Choose the embedding model for semantic search:
1. Use global default (recommended)
2. Use BGE-large-en-v1.5 (high accuracy, requires GPU)
3. Use lightweight model (faster, less accurate)
4. Custom model name
```

### Database Schema

Server configurations stored in `server_configs` table:

```sql
CREATE TABLE server_configs (
    server_id TEXT PRIMARY KEY,
    message_processing_error_handling TEXT DEFAULT 'skip',
    embedding_model_name TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## GPU Requirements

### Hardware Prerequisites
- NVIDIA GPU with CUDA support
- Minimum 2GB VRAM (BGE-large-en-v1.5 requires ~1.3GB)
- CUDA driver version 11.8+ recommended

### Software Dependencies
- PyTorch with CUDA support (automatically installed via requirements.txt)
- sentence-transformers>=2.2.0
- CUDA runtime libraries (bundled with PyTorch)

### CUDA Detection
The system automatically detects CUDA availability and enforces GPU requirement for BGE models:

```python
if torch.cuda.is_available():
    self.device = "cuda"
    logger.debug(f"CUDA available, using GPU for {model_name}")
else:
    logger.error(f"CUDA not available but required for {model_name}")
    raise EmbeddingError("BGE-large-en-v1.5 requires GPU but CUDA is not available")
```

**Important**: The BGE-large-en-v1.5 model strictly requires GPU/CUDA. If CUDA is not available, the system raises an `EmbeddingError` rather than falling back to CPU, ensuring consistent high-performance operation.

## Startup Optimization

### Automatic Model Preloading

The application now preloads the BGE embedding model during startup to eliminate Discord heartbeat blocking:

```python
# In main.py startup sequence
logger.info("🔤 Preloading embedding models...")
try:
    from src.db.embedders import preload_embedder
    await preload_embedder("BAAI/bge-large-en-v1.5")
    logger.info("✅ BGE embedding model preloaded successfully")
except Exception as e:
    logger.warning(f"Failed to preload BGE embedding model: {e}")
    logger.info("BGE model will be loaded on first use (may cause delays)")
```

**Benefits:**
- Eliminates runtime model loading that causes Discord connection timeouts
- Reduces first message processing latency from ~10s to <1s
- Prevents multiple redundant model loads (17+ instances → 1 singleton)
- Maintains responsive Discord bot connections

### Singleton Management

The singleton pattern ensures optimal memory usage:

```python
from src.db.embedders.text_embedder import get_loaded_models, clear_embedder_cache

# Check what models are currently loaded
loaded_models = get_loaded_models()
print(f"Loaded models: {loaded_models}")

# Clear cache if needed (testing/debugging only)
clear_embedder_cache()
```

## Installation

### Dependencies

The following dependencies are automatically installed via `requirements.txt`:

```txt
# CUDA Installation Instructions:
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
--extra-index-url https://download.pytorch.org/whl/cu128

sentence-transformers>=2.2.0
torch>=2.0.0
torchvision
torchaudio
```

### Model Download

Models are automatically downloaded on first use via sentence-transformers. No manual download required.

**Download Location:** `~/.cache/huggingface/transformers/`

## Usage

### Automatic Integration

The embedding system integrates automatically with existing message processing:

1. **Message Storage**: Uses configured embedding model via `get_collection()`
2. **Search Operations**: Maintains model consistency for query/document matching
3. **Server Isolation**: Each server maintains its own embedding configuration

### Manual Configuration

```python
from src.db.embedders.text_embedder import get_text_embedder, preload_embedder
from src.message_processing.storage import get_collection

# Preload model asynchronously (recommended for startup)
await preload_embedder("BAAI/bge-large-en-v1.5")

# Get embedder instance (will reuse preloaded singleton)
embedder = get_text_embedder("BAAI/bge-large-en-v1.5")

# Get collection - automatic server-specific embedder detection
collection = get_collection(server_id, "messages")

# Or use explicit custom embedder
collection = get_collection(server_id, "messages", custom_embedder=embedder)
```

**Note**: The `get_collection()` function automatically detects and uses the configured embedding model for each server, eliminating the need to manually specify embedders in most cases.

## Performance Characteristics

### BGE-large-en-v1.5 Specifications
- **Model Size**: 335M parameters (~1.3GB VRAM)
- **Embedding Dimensions**: 1024
- **Max Sequence Length**: 512 tokens
- **Performance**: Top-tier accuracy on MTEB benchmark (64.23 average)

### Fallback Performance
- **Default Model**: ONNX MiniLM-L6-V2 (384 dimensions)
- **CPU Optimized**: Efficient for consumer hardware
- **Memory Usage**: ~100MB RAM

### Performance Targets
- **Indexing**: 50+ messages reliably
- **Query Response**: Sub-5-second search times
- **Hardware**: Stable on RTX 3090, 24GB RAM

## Error Handling & Fallbacks

### GPU Unavailable
When CUDA is not detected for BGE models:

```
WARNING - Failed to load custom embedder BAAI/bge-large-en-v1.5: EmbeddingError: BGE-large-en-v1.5 requires GPU but CUDA is not available
INFO - Falling back to default embedder for server 1234567890
```

The system gracefully falls back to ChromaDB's default embedding function when custom models fail to load, ensuring continued operation.

### Model Loading Failures
When model download/loading fails:

```python
try:
    # Use singleton embedder to prevent multiple model loading
    embedder = get_text_embedder(server_embedding_model)
    logger.debug(f"Using singleton embedder {server_embedding_model} for server {server_id}")
except EmbeddingError as e:
    logger.warning(f"Failed to load custom embedder {server_embedding_model}: {e}")
    logger.info(f"Falling back to default embedder for server {server_id}")
    embedder = None
```

**Note**: The actual implementation catches `EmbeddingError` (not `RuntimeError`) and uses `logger.debug()` for successful loads to reduce log verbosity during normal operation.

### Backward Compatibility
- Existing servers continue using default embeddings
- New `embedding_model_name` column added with NULL default
- No breaking changes to existing functionality

## Troubleshooting

### Common Issues

#### 1. CUDA Not Available
**Symptoms:** `torch.cuda.is_available()` returns False

**Solutions:**
- Verify NVIDIA GPU drivers installed
- Check PyTorch installation: `pip install torch --index-url https://download.pytorch.org/whl/cu128`
- Verify CUDA runtime: `nvidia-smi`

#### 2. Model Download Failures
**Symptoms:** Connection errors during first model load

**Solutions:**
- Check internet connectivity
- Clear HuggingFace cache: `rm -rf ~/.cache/huggingface/`
- Manual download: `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"`

#### 3. Memory Issues
**Symptoms:** CUDA out of memory errors

**Solutions:**
- Close other GPU applications
- Use smaller model variant (bge-base-en-v1.5 or bge-small-en-v1.5)
- Check VRAM usage: `nvidia-smi`

#### 4. Multiple Model Loading (Legacy Issue - Fixed)
**Symptoms:** Multiple "Loading BAAI/bge-large-en-v1.5" log entries, Discord heartbeat timeouts

**Solution:** 
This issue is resolved with the singleton pattern implementation (commit `0da47f2`). The singleton pattern ensures:
- Each model is loaded only once per application lifecycle
- Log messages show "singleton instance" for proper caching
- Reused instances show "Reusing existing singleton embedder instance"

If still experiencing issues:
- Verify you're using the latest code with singleton pattern
- Check logs for "singleton instance" messages indicating proper caching  
- Use `get_loaded_models()` to verify only one instance is loaded per model

### Diagnostic Commands

```bash
# Check CUDA availability
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"

# Verify PyTorch version
python -c "import torch; print('PyTorch version:', torch.__version__)"

# Test model loading and singleton pattern
python -c "from src.db.embedders.text_embedder import get_text_embedder, get_loaded_models; e1=get_text_embedder('BAAI/bge-large-en-v1.5'); e2=get_text_embedder('BAAI/bge-large-en-v1.5'); print('Singleton working:', e1 is e2); print('Loaded models:', get_loaded_models())"

# Check server configuration
python -c "from src.db.setup_db import get_server_embedding_model; print('Server 123 model:', get_server_embedding_model(123))"

# Test preloading function
python -c "import asyncio; from src.db.embedders import preload_embedder; asyncio.run(preload_embedder('BAAI/bge-large-en-v1.5'))"
```

## Future Enhancements

### Planned Features
- **Model Hot-swapping**: Change embedding models without restart
- **Batch Processing**: Optimize for large message backlogs
- **Model Caching**: Intelligent model memory management
- **Performance Metrics**: Embedding generation timing and throughput

### Extension Points
- **Custom Models**: Support for fine-tuned domain-specific models
- **Multi-language**: International embedding model support
- **Hybrid Search**: Combine keyword and semantic search
- **Vector Compression**: Reduce storage requirements

## Related Documentation

- [Database Management](database-management.md) - ChromaDB integration details
- [Configuration and Environment](configuration-and-environment.md) - Environment variable setup
- [Message Processing Pipeline](message-processing-pipeline.md) - Integration with message flow

## Implementation Reference

**Original Commit**: `21323de` - feat: implement custom BGE-large-en-v1.5 embedding model with GPU support
**Optimization Commit**: `0da47f2` - feat: optimize BGE embedding system with singleton pattern and async preloading  
**Documentation Commit**: `def4dbf` - docs: comprehensive documentation update for dual model system and custom embeddings

**Key Files:**
- `src/db/embedders/text_embedder.py` - Core embedding implementation with singleton pattern
- `src/db/embedders/__init__.py` - Module exports including preloading functions
- `src/message_processing/storage.py` - Optimized collection management with embedder reuse
- `main.py` - Startup sequence with async model preloading
- `src/setup/server_setup.py` - Configuration UI
- `src/db/setup_db.py` - Database integration
- `.claude/agents/embedding-model-manager.md` - Maintenance subagent

**Performance Improvements:**
- Eliminated 17+ redundant BGE model loads through singleton pattern
- Added async startup preloading to prevent Discord connection timeouts
- Implemented thread-safe model caching for concurrent access
- Reduced first message processing latency from ~10s to <1s