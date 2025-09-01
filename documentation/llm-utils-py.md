# src/llm/utils.py Documentation

## Purpose
Model management utilities for Ollama integration. Provides centralized functions for model availability checking, downloading, health monitoring, and client management to support all LLM agents in the system.

## What It Does
1. **Ollama Client Management**: Creates and configures Ollama client instances
2. **Model Availability**: Ensures required models are downloaded and accessible
3. **Health Monitoring**: Validates model responsiveness and availability
4. **Model Information**: Retrieves metadata about installed models
5. **Error Handling**: Graceful handling of connection and model management errors

## Key Functions

### `get_ollama_client()`
**Purpose**: Factory function for creating configured Ollama client instances

**Returns**: Configured `ollama.Client` instance

**Configuration**:
- Uses `OLLAMA_HOST` environment variable if set
- Falls back to default localhost connection
- Reusable across all LLM operations

### `ensure_model_available(model_name)`
**Purpose**: Validates model existence and downloads if missing

**Parameters**:
- `model_name`: Name of the Ollama model to check/download

**Process**:
1. Lists available models on Ollama instance
2. Checks if target model exists in available models
3. Downloads model if not found locally
4. Logs progress and completion status

**Error Handling**: Raises specific exceptions for connection, timeout, and model issues

### `health_check(model_name)`
**Purpose**: Validates model responsiveness with test inference

**Parameters**:
- `model_name`: Name of the model to test

**Returns**: Boolean indicating model health status

**Process**:
- Sends minimal test prompt to model
- Limits response tokens for efficiency
- Returns success/failure status

### `get_model_info(model_name)`
**Purpose**: Retrieves detailed metadata about installed model

**Parameters**:
- `model_name`: Name of the model to query

**Returns**: Dictionary with model information or empty dict if not found

**Information Includes**:
- Model size and architecture details
- Download status and version
- Available capabilities

## Error Handling Strategy

### Exception Types Caught
- **ConnectionError**: Ollama service unavailable
- **TimeoutError**: Model operations timeout
- **OSError**: System-level file/network issues
- **ValueError**: Invalid model names or parameters
- **KeyError**: Missing model metadata fields
- **RuntimeError**: General Ollama runtime issues

### Fallback Behavior
- Graceful degradation with detailed error logging
- No silent failures - all errors are logged and re-raised
- Consistent error messaging across all functions

## Current Implementation Status

**Model Management**: Fully implemented with comprehensive error handling
**Client Factory**: Fully implemented with environment configuration
**Health Monitoring**: Fully implemented with test inference
**Model Discovery**: Fully implemented with robust metadata handling
**Error Handling**: Comprehensive exception handling with specific error types

## Integration Points

### Used By
- `src/llm/chat_completion.py` - Uses `get_ollama_client()` for API calls
- `src/llm/agents/dm_assistant.py` - Uses `ensure_model_available()` and `health_check()`
- All future LLM agents - Reusable across entire system

### Dependencies
- `ollama` package for model management
- Environment variables for configuration
- Logging system for error tracking

## Configuration

### Environment Variables
- **`OLLAMA_HOST`**: Custom Ollama server URL (optional)
- **`LLM_MODEL_NAME`**: Default model name from settings

### Usage Example
```python
from llm.utils import ensure_model_available, health_check, get_ollama_client

# Ensure model is available
ensure_model_available("llama3.2")

# Check model health
is_healthy = health_check("llama3.2")

# Get client for operations
client = get_ollama_client()
```

## Design Decisions

### Why Separate Utility Module?
- **Reusability**: Shared across all LLM agents and components
- **Single Responsibility**: Focused solely on model management
- **Configuration**: Centralized Ollama configuration
- **Error Handling**: Consistent error patterns across system

### Why Factory Pattern for Client?
- **Configuration**: Centralized client configuration
- **Environment Support**: Easy switching between Ollama instances
- **Resource Management**: Consistent client creation patterns

### Why Explicit Model Downloading?
- **Fail-Fast**: Immediate feedback if models unavailable
- **User Experience**: Clear progress indication for large model downloads
- **Reliability**: Ensures models available before operation attempts

## Future Extensibility

This utility module is designed for easy extension:
- **Multiple Ollama Instances**: Support for distributed model serving
- **Model Caching**: Intelligent model download and caching strategies
- **Performance Monitoring**: Model performance metrics and optimization
- **Version Management**: Model version tracking and updates
- **Resource Management**: GPU/CPU resource allocation and monitoring
- **Alternative Backends**: Support for other LLM serving platforms

## Performance Considerations
- **Client Reuse**: Factory pattern enables efficient client reuse
- **Lazy Loading**: Models downloaded only when required
- **Health Caching**: Health check results could be cached for performance
- **Parallel Operations**: Functions designed for concurrent usage across agents
