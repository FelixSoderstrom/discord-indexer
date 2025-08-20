# message_processing/processor.py

## Purpose

Main message processing pipeline coordinator that orchestrates the complete Discord message processing workflow. This module provides the `MessagePipeline` class which serves as the central orchestrator for all message processing operations.

## Key Components

### MessagePipeline Class

The core class that coordinates message processing through the complete pipeline workflow.

**Initialization:**
- Creates processing statistics tracking
- No database connection management (handled separately)
- Lightweight initialization focused on coordination logic

**Content Analysis:**
- `_check_message_content()` - Analyzes message to determine processing requirements
- Detects: text content, images, URLs, mentions, empty messages
- Returns analysis dictionary for routing decisions

**Processing Router:**
- `_route_message_processing()` - Routes messages through appropriate processing steps
- Conditional processing based on content analysis
- Always processes metadata, conditionally processes embeddings and extractions

**Main Processing Method:**
- `process_message()` - Main entry point for all message processing
- Handles complete workflow from analysis through storage
- Returns boolean indicating readiness for next message (serial processing)
- Implements comprehensive error handling with fail-fast behavior

**Statistics Tracking:**
- Tracks messages processed and failed counts
- Calculates success rates
- Provides processing statistics via `get_processing_stats()`

## Processing Flow

1. **Message Analysis**: Determine what processing steps are required
2. **Empty Message Handling**: Skip processing for empty messages
3. **Conditional Routing**: Route through appropriate processing modules
4. **Storage Coordination**: Coordinate storage of all processed components
5. **Result Reporting**: Return success/failure status for next message readiness

## Error Handling

- Comprehensive try-catch blocks around all processing steps
- Failed processing increments failure counter and returns False
- No fallback mechanisms - failures are reported up to calling code
- Processing statistics maintained for all outcomes

## Dependencies

- `embedding.py` - For text and image embedding processing
- `extraction.py` - For URL and mention extraction processing
- `metadata.py` - For metadata preparation processing
- `storage.py` - For database storage coordination

## Current Status

**Fully Implemented:**
- Complete pipeline coordination logic
- Content analysis and routing
- Error handling and statistics tracking
- Integration with all processing modules

**Architecture Ready For:**
- Real processing module implementations
- Performance optimization
- Extended content analysis capabilities
