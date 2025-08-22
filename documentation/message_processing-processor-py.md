# message_processing/processor.py

## Purpose

Main message processing pipeline coordinator that orchestrates the unified Discord message processing workflow. This module provides the `MessagePipeline` class which serves as the central orchestrator for batch processing of both historical and real-time messages with chronological ordering and producer-consumer coordination.

## Key Components

### MessagePipeline Class

The core class that coordinates message processing through the complete pipeline workflow.

**Initialization:**
- Accepts optional `completion_event` for async coordination with bot
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

**Chronological Sorting:**
- `_sort_messages_chronologically()` - Sorts messages by timestamp for proper order
- Handles messages from multiple channels fetched in parallel
- Ensures chronological consistency across entire system

**Main Processing Method:**
- `process_messages()` - Main entry point for batch message processing
- Unified interface for both historical and real-time messages
- Sorts messages chronologically before processing
- Processes each message sequentially within batch
- Implements producer-consumer coordination via asyncio.Event
- Returns boolean indicating entire batch success/failure

**Statistics Tracking:**
- Tracks messages processed and failed counts
- Calculates success rates
- Provides processing statistics via `get_processing_stats()`

## Processing Flow

1. **Batch Validation**: Handle empty batches and validate input
2. **Chronological Sorting**: Sort messages by timestamp for proper processing order
3. **Sequential Processing**: Process each message in the sorted batch
4. **Message Analysis**: Determine what processing steps are required for each message
5. **Empty Message Handling**: Skip processing for empty messages
6. **Conditional Routing**: Route through appropriate processing modules
7. **Storage Coordination**: Coordinate storage of all processed components
8. **Completion Signaling**: Signal batch completion via asyncio.Event for coordination
9. **Result Reporting**: Return success/failure status for entire batch

## Error Handling

- Comprehensive try-catch blocks around all batch processing steps
- Any message failure within batch fails entire batch (atomic processing)
- Failed processing increments failure counter by entire batch size and returns False
- Producer-consumer coordination ensures completion signal even on failure
- No fallback mechanisms - failures are reported up to calling code
- Processing statistics maintained for all outcomes

## Dependencies

- `embedding.py` - For text and image embedding processing
- `extraction.py` - For URL and mention extraction processing
- `metadata.py` - For metadata preparation processing
- `storage.py` - For database storage coordination

## Current Status

**Fully Implemented:**
- Unified batch processing interface for historical and real-time messages
- Chronological message sorting across multiple channels
- Producer-consumer coordination with asyncio.Event signaling
- Complete pipeline coordination logic with backpressure control
- Content analysis and routing
- Error handling and statistics tracking with atomic batch processing
- Integration with all processing modules

**Architecture Ready For:**
- Real processing module implementations
- Performance optimization
- Extended content analysis capabilities
- Future timestamp-based resume functionality
