# Config Validator Agent Instructions

## Key Areas of Focus
- `src/config/settings.py` - Pydantic settings class with dual model configuration
- `.env` - Environment variables with dual model names and Discord credentials
- `requirements.txt` - Dependencies including CUDA PyTorch and LangChain integration
- `src/ai/model_manager.py` - Dual model loading and validation
- `src/db/setup_db.py` - Database initialization and server-specific configurations
- `src/setup/server_setup.py` - Server configuration system

## Specific Responsibilities

### Environment Validation
- Validate Python version compatibility (Target: 3.10.6, compatible with 3.10+)
- Check dual model hardware requirements (8-12GB VRAM for simultaneous text+vision models)
- Verify Ollama server accessibility and configuration
- Validate CUDA PyTorch installation for GPU-accelerated embeddings

### Pydantic Settings Management
- Validate BotSettings structure with dual model configuration:
  - `DISCORD_TOKEN`: Required Discord bot token
  - `TEXT_MODEL_NAME`: Text processing model (e.g., llama3.2:3b)
  - `VISION_MODEL_NAME`: Vision processing model (e.g., minicpm-v)
  - `EMBEDDING_MODEL_NAME`: Embedding model with server-specific override capability
  - `COMMAND_PREFIX`, `DEBUG`, `LANGCHAIN_VERBOSE`: Optional settings with defaults
- Ensure proper environment variable mapping with case-sensitive matching
- Test configuration loading and validation through settings instantiation
- Validate Discord intents configuration via `get_intents` property

### Dual Model Configuration Validation
- Validate simultaneous text and vision model accessibility via Ollama
- Check model availability and automatic downloading capability
- Verify ModelManager initialization and dual model loading patterns
- Test health checking for both models with response time validation
- Validate 30-minute keep-alive configuration for memory persistence
- Ensure proper error handling for model loading failures (fails hard, no fallback)

### Database and Server Configuration Validation
- Validate ChromaDB client initialization with server-specific isolation
- Check SQLite server configuration database structure and accessibility
- Verify server-specific database directory creation (`databases/{server_id}/chroma_data`)
- Test server configuration caching and validation patterns
- Validate embedding model override functionality per server
- Check conversation database initialization and structure

### Dependency Management
- Validate requirements.txt structure with CUDA installation instructions
- Check core dependency versions:
  - `discord.py==2.6.0`
  - `pydantic==2.11.7` and `pydantic-settings==2.10.1`
  - `chromadb==1.0.20`
  - `ollama>=0.3.0`
  - LangChain ecosystem packages
  - PyTorch CUDA installation compatibility
- Identify missing or conflicting packages with version compatibility
- Verify virtual environment isolation and activation

### Security Configuration
- Validate Discord token handling (environment-only, never logged)
- Check file permissions for database directories and log files
- Ensure no secrets exposed in logging or error messages
- Validate secure settings instantiation patterns throughout codebase
- Check Discord intents configuration for minimal required permissions

## Implementation Process
1. **Analysis Phase**: Examine current settings structure, model configuration, and database patterns
2. **Environment Validation Phase**: Test environment variable loading, model accessibility, and hardware compatibility
3. **Dependency Validation Phase**: Check package versions, CUDA installation, and virtual environment setup
4. **Database Validation Phase**: Test ChromaDB initialization, SQLite configuration DB, and server-specific isolation
5. **Integration Validation Phase**: Verify ModelManager initialization, dual model loading, and health checking
6. **Reporting Phase**: Provide detailed validation results with specific configuration recommendations
7. **Recommendation Phase**: Suggest fixes for identified issues with codebase-specific patterns

## Coordination with Other Components

### ModelManager Integration
- Coordinate with ModelManager for dual model validation
- Validate proper model loading sequence (vision first, then text)
- Check keep-alive configuration and memory management patterns

### Database Setup Coordination
- Work with database initialization patterns in `src/db/setup_db.py`
- Validate server-specific ChromaDB client caching
- Check SQLite configuration database schema and accessibility

### Server Configuration System
- Validate server configuration workflow and caching patterns
- Check terminal UI configuration process compatibility
- Ensure proper server configuration validation before message processing

## Testing Approach
- Create validation scripts for dual model accessibility via Ollama
- Test Pydantic settings instantiation with various environment configurations
- Validate database initialization with proper error handling
- Check server configuration database operations and caching
- Test ModelManager health checking and dual model loading
- Verify virtual environment dependency isolation
- Test CUDA PyTorch installation validation
- Validate Discord token security and intents configuration

## Hardware and Performance Validation
- Check VRAM requirements for dual model operation (8-12GB target)
- Validate system memory requirements (24GB recommended for dual models)
- Test SSD storage performance for database operations
- Verify GPU utilization for embedding models and local LLM inference
- Check network connectivity for Discord API and Ollama communication

## Error Handling Patterns Validation
- Validate specific exception handling (no broad `Exception` catching)
- Check ChromaError handling for database initialization
- Verify ConnectionError and TimeoutError patterns for model operations
- Test graceful failure modes for configuration loading
- Validate logging patterns with appropriate detail levels without secret exposure