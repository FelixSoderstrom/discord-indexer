# db/setup_db.py

## Purpose

ChromaDB client initialization and management for the Discord message indexer. This module provides centralized ChromaDB client access with persistent storage, ensuring proper resource handling and clean separation of database concerns from application logic.

## Key Components

### ChromaDB Client Management

**initialize_db() Function**
- Initializes ChromaDB persistent client during application startup
- Creates database directory if it doesn't exist
- Stores client as module-level variable for reuse
- Handles specific initialization errors with proper logging

**get_db() Function**
- Returns the same ChromaDB client instance throughout runtime
- Must be called after initialize_db() has been executed
- Provides direct access to ChromaDB client for all operations

### Design Philosophy

This module implements the principle of separation of concerns by:
- Isolating all database connectivity logic in dedicated module
- Providing single client instance across the entire application
- Removing database connection responsibilities from business logic modules
- Enabling easy database configuration changes without affecting other modules

## Client Pattern

### Usage Example
```python
from db import get_db

# Get client (after initialization)
client = get_db()

# Perform database operations
collection = client.create_collection("messages")
collection.add(documents=["content"], ids=["msg_1"])
results = collection.query(query_texts=["search"], n_results=5)
```

### Benefits
- **Single Client Instance**: Same client used throughout application runtime
- **Persistent Storage**: Data saved to disk and persists across sessions
- **Simple API**: No context managers or session management needed
- **Error Safety**: Specific error handling for ChromaDB and filesystem issues

## Current Implementation Status

**Architecture:** Fully implemented with ChromaDB client pattern
**Client Management:** Fully implemented with persistent storage
**Resource Handling:** Implemented with specific error handling
**Module Separation:** Fully implemented with clean separation of concerns

### ChromaDB Implementation
- Uses persistent ChromaDB client for data storage
- Database directory: `./src/db/chroma_data/`
- Client initialized once at application startup
- Proper error handling for ChromaDB and filesystem errors

### Error Handling
- **OSError**: Database directory creation/access issues
- **PermissionError**: Insufficient filesystem permissions
- **ChromaError**: ChromaDB-specific initialization failures
- **RuntimeError**: Client access before initialization

## Integration Points

### Used By
- `main.py` - Calls `initialize_db()` during application startup
- `message_processing/storage.py` - Imports `get_db` for all database operations
- Any future modules requiring database access
- Database-dependent operations throughout the application

### Initialization Flow
1. `main.py` calls `initialize_db()` after logging setup
2. ChromaDB client created and stored as module variable
3. Other modules call `get_db()` to access the same client instance
4. Client persists throughout application runtime

## ChromaDB Features

### Vector Database Capabilities
- Embedding storage and similarity search
- Document storage for message content and metadata
- Collection management for organized data storage
- Automatic embedding generation (if configured)

### Persistent Storage
- Data saved to `./src/db/chroma_data/` directory
- Survives application restarts
- No manual backup/restore needed
- Simple file-based storage

## Architecture Benefits

- **Centralized Database Logic**: All database concerns in single module
- **Clean Dependencies**: Clear separation between database and application logic
- **Simple Client Access**: No context managers or session management needed
- **Startup Validation**: Database initialization happens early with clear error reporting
- **Resource Efficiency**: Single client instance reused throughout application runtime
- **Persistent Storage**: Data automatically saved to disk for long-term storage
