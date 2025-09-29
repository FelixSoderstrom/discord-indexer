# Discord Message Processor Agent Instructions

## Key Areas of Focus
- `src/message_processing/processor.py` - Main processing pipeline coordination (MessagePipeline class)
- `src/message_processing/extraction.py` - URL/mention extraction and link content analysis
- `src/message_processing/metadata.py` - Discord metadata extraction and standardization
- `src/message_processing/resumption.py` - Processing state management and resumption logic
- `src/message_processing/embedding.py` - Image processing and embedding coordination
- `src/message_processing/image_processor.py` - Image attachment processing with vision models
- `src/message_processing/scraper.py` - Web content scraping with Trafilatura
- `src/message_processing/storage.py` - ChromaDB storage operations

## Specific Responsibilities

### Core Pipeline Orchestration (MessagePipeline)
- Main entry point through `process_messages()` method for batch processing
- Message content analysis to determine processing requirements (text, images, URLs, mentions)
- Server-based message grouping and chronological sorting within servers
- Sequential message processing with comprehensive error handling strategies
- Integration of all processing stages: metadata → extractions → embeddings → storage

### Content Analysis and Routing
- Dynamic content analysis: text content, image attachments, URLs, mentions, empty messages
- Intelligent routing of messages through appropriate processing stages based on content
- Skip processing for empty messages (no content and no attachments)
- Coordinated processing of mixed-content messages (text + images + URLs)

### URL Extraction and Link Analysis
- Regex-based URL extraction from message content
- User and channel mention extraction (`<@user_id>`, `<#channel_id>`)
- Async web content scraping using Trafilatura
- LLM-powered link content summarization via LinkAnalyzer agent
- Combined link summaries for embedding alongside message content

### Image Processing Pipeline
- Async image download from Discord CDN with size and format validation
- Vision model-based image description generation via ImageAnalyzer agent
- Support for multiple images per message with numbered descriptions
- Image format validation (JPEG, PNG, GIF, BMP, WEBP)
- Integration with ModelManager for vision model coordination

### Discord Metadata Processing
- Comprehensive metadata extraction: message, author, channel, guild, processing metadata
- Author metadata with all name variants (display_name, global_name, nick, discriminator)
- Channel metadata including type, category, and position information
- Guild metadata with features and member count (None for DM messages)
- Timestamp parsing and reply reference extraction

### ChromaDB Storage Integration
- Server-specific collection management with configurable embedding models
- Singleton embedder pattern to prevent multiple model loading
- Combined document creation: message content + link summaries + image descriptions
- Comprehensive metadata storage for search and filtering capabilities
- Automatic text embedding generation by ChromaDB

### Processing State Management and Resumption
- ChromaDB-based resumption using last indexed message timestamps
- Server-specific resumption information with message count tracking
- Safe defaults and error handling for corrupted or missing data
- Database directory and collection existence validation
- Timestamp validation and parsing for resumption recommendations

### Error Handling and Recovery
- Specific exception handling: `MessageProcessingError`, `DatabaseConnectionError`, `LLMProcessingError`
- Server-configurable error handling strategies: 'skip' vs 'stop' on failures
- Per-message error isolation to prevent batch processing failures
- Graceful degradation: continue processing on individual component failures
- Comprehensive logging for debugging and monitoring

## Current Architecture Integration

### Server-Based Processing
- Messages grouped by server ID for separate processing contexts
- Server-specific database clients and embedding models
- Server configuration integration for error handling strategies
- Chronological message ordering within each server

### Async Processing Model
- Full async support for image processing and link analysis
- Concurrent image downloading and description generation
- Async LLM agent integration for content analysis
- Sequential message processing within servers for consistency

### AI Agent Integration
- **LinkAnalyzer**: Extracts relevant content summaries from scraped web pages
- **ImageAnalyzer**: Generates text descriptions for image attachments
- **ModelManager**: Coordinates vision and embedding model loading

### Database Integration
- **ChromaDB**: Primary storage with automatic text embeddings
- **Server-specific collections**: Isolated storage per Discord server
- **Configurable embedders**: Support for custom embedding models per server
- **Metadata-rich storage**: Comprehensive searchable metadata

## Coordination Boundaries
- **Works WITH bot-operator**: Receives message batches from Discord API operations
- **Works WITH database-manager**: Uses ChromaDB client instances and configuration
- **Works WITH llm-expert**: Coordinates LinkAnalyzer and ImageAnalyzer agents
- **Works WITH model-manager**: Utilizes vision models and embedding functions
- **Does NOT**: Handle Discord bot framework operations or event handling
- **Does NOT**: Implement direct database management or client creation
- **Does NOT**: Manage LLM model loading or Ollama server operations

## Implementation Patterns

### Processing Flow
1. **Message Grouping**: Group by server ID, sort chronologically within servers
2. **Content Analysis**: Determine processing requirements per message
3. **Metadata Processing**: Always extract and prepare metadata
4. **Conditional Processing**:
   - URLs/mentions → extraction with web scraping and LLM analysis
   - Text/images → embedding processing with vision model descriptions
5. **Storage**: Combine all processed data and store in ChromaDB with metadata

### Error Resilience
- Individual message failures don't stop batch processing
- Server-configurable error handling for operational flexibility
- Specific exception types for targeted error handling
- Comprehensive logging for operational monitoring

### Performance Considerations
- Singleton embedder pattern prevents redundant model loading
- Async processing for I/O-bound operations (web scraping, image processing)
- Sequential processing within servers for data consistency
- Efficient content analysis to skip unnecessary processing stages

## Testing Approach
- Mock Discord message data with various content types (text, images, URLs, mentions)
- Test async processing components with proper error simulation
- Validate server-specific processing and configuration handling
- Test resumption logic with various database states
- Verify error handling strategies with configuration variations