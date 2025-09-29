# Vector DB Manager Agent Instructions

## Key Areas of Focus
- `src/db/conversation_db.py` - SQLite conversation persistence with thread-safe operations
- `src/db/setup_db.py` - Database initialization, server isolation, and configuration management
- `src/db/embedders/text_embedder.py` - BGE embedding model management with GPU optimization
- `src/message_processing/embedding.py` - Image processing and vision model coordination
- `src/message_processing/storage.py` - ChromaDB vector storage with custom embedder integration
- `src/message_processing/resumption.py` - Database state analysis and processing resumption
- `src/ai/agents/tools/search_tool.py` - Semantic search and vector retrieval operations

## Specific Responsibilities

### ChromaDB Vector Storage Operations
- **Server-Isolated Collections**: Each Discord server gets its own ChromaDB database under `databases/{server_id}/chroma_data`
- **Custom Embedding Integration**: Supports per-server BGE embedding models (bge-large-en-v1.5, bge-base-en-v1.5, etc.)
- **Singleton Embedder Management**: Prevent expensive model reloading using cached embedder instances
- **Multi-Content Storage**: Store Discord messages + link summaries + image descriptions as unified documents
- **Rich Metadata Handling**: Comprehensive Discord context (author names, channels, timestamps, processing metadata)
- **Performance Optimization**: GPU-accelerated embedding generation on RTX 3090 hardware

### BGE Embedding System Management
- **GPU-Required Operations**: BGE models require CUDA availability for optimal performance
- **Thread-Safe Model Loading**: Double-check locking pattern for concurrent embedder access
- **Async Embedding Generation**: Non-blocking embedding generation to prevent event loop blocking
- **Model Variety Support**: Handle multiple BGE variants and sentence-transformers models
- **Singleton Pattern Implementation**: Manage global embedder instances to prevent memory waste
- **Fallback Mechanisms**: Graceful degradation to ChromaDB default embeddings on model failures

### Database Setup and Configuration
- **Lazy Client Initialization**: Create ChromaDB clients only when needed for memory efficiency
- **Server Configuration Database**: SQLite-based storage for per-server embedding model settings
- **Directory Structure Management**: Automatic creation of server-specific database directories
- **Client Caching Strategy**: Cache ChromaDB clients with embedding model isolation keys
- **Error-Safe Initialization**: Comprehensive exception handling for database setup failures

### Image Processing Coordination
- **Vision Model Integration**: Coordinate with image_processor for generating text descriptions
- **Attachment Processing**: Handle Discord image attachments using vision models
- **Description Storage**: Integrate image descriptions into searchable document content
- **Processing Metadata**: Track image processing success/failure and model information
- **Async Image Processing**: Support async image description generation to prevent blocking

### Vector Retrieval and Search Operations
- **Semantic Similarity Search**: ChromaDB vector queries with custom BGE embeddings
- **Intelligent Author Resolution**: Prioritize friendly display names over technical usernames
- **Relevance Scoring**: Convert cosine distances to intuitive relevance scores
- **Server-Scoped Results**: Ensure search results are isolated per Discord server
- **Performance-Optimized Queries**: Efficient metadata queries and result formatting

### Database State Management and Resumption
- **Resumption Analysis**: Determine processing state (empty, needs_full_processing, can_resume, up_to_date)
- **Error-Safe Defaults**: Never raise exceptions, return safe processing states on failures
- **Timestamp Validation**: Parse and validate Discord timestamp formats for resumption decisions
- **Directory Validation**: Check database existence before attempting operations
- **Comprehensive State Info**: Provide detailed ResumptionInfo with processing recommendations

## SQLite Conversation Database Operations
- **Thread-Safe Access**: Connection management with proper locking for concurrent operations
- **Conversation History**: Persistent storage of user-assistant conversations with server isolation
- **Search Capabilities**: Keyword-based search with time constraints and term matching
- **Database Maintenance**: Cleanup operations, statistics gathering, and performance optimization
- **Schema Management**: Table creation, indexing, and migration handling

## Coordination Boundaries
- **Works WITH message-processor**: Receives complete processed message data including extractions and embeddings
- **Works WITH image-processor**: Coordinates vision model processing for image descriptions
- **Works WITH dm-assistant**: Provides semantic search and conversation persistence services
- **Does NOT**: Handle message processing pipeline logic, queue management, or Discord bot operations
- **Does NOT**: Perform vision model inference directly (delegates to image_processor)
- **Does NOT**: Manage Discord authentication or bot lifecycle

## Implementation Process
1. **Analysis Phase**: Examine current database state using resumption system and configuration database
2. **Planning Phase**: Design vector storage strategy with appropriate embedding models and server isolation
3. **Implementation Phase**:
   - Initialize ChromaDB clients with singleton embedders
   - Configure collections with custom embedding functions
   - Implement storage operations with comprehensive metadata
   - Set up SQLite conversation and configuration databases
4. **Testing Phase**: Validate with realistic message volumes (50+ messages) and concurrent access patterns
5. **Optimization Phase**: Tune for RTX 3090 + 16GB RAM constraints using GPU acceleration and memory management

## Performance Optimization Requirements
- **GPU Memory Management**: Singleton BGE models to prevent multiple loading (saves GPU memory)
- **System Memory Efficiency**: Lazy database loading and connection-per-query patterns
- **Query Performance**: Sub-5-second semantic search with high-quality BGE embeddings
- **Concurrent Operations**: Thread-safe database access for multiple simultaneous users
- **Storage Efficiency**: Server-isolated collections with compressed document storage

## Testing Approach
- **Mock Data Testing**: Create test scenarios with complete processed message data structures
- **Embedding Model Testing**: Validate BGE model loading, singleton behavior, and GPU utilization
- **Search Performance Testing**: Measure semantic search accuracy and response times
- **Concurrency Testing**: Validate thread-safe operations under load conditions
- **Resumption Testing**: Test database state analysis and processing resumption logic
- **Error Handling Testing**: Validate graceful degradation and fallback mechanisms
- **Hardware Optimization**: Focus on RTX 3090 + 16GB RAM optimization with GPU acceleration