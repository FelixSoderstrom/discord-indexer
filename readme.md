# Discord-Indexer

A Discord bot that indexes server message history and provides intelligent search through direct messages using local LLM processing.

## What it does

The bot extracts all messages from Discord channels, converts them to searchable vectors, and allows users to query the conversation history through natural language. Instead of manually scrolling through months of chat history, users can ask questions like "What did we decide about the deployment schedule?" and get relevant message context with source links.

## Core Features

- **Message Indexing**: Automatically processes Discord channel history with metadata preservation
- **Semantic Search**: Vector-based search using sentence transformers for contextual relevance
- **LLM Integration**: Local Mistral 7B model for response generation and context synthesis
- **DM Interface**: Query the indexed content through direct messages with the bot
- **Voice Processing**: Speech-to-text and text-to-speech support via Chatterbox integration
- **Real-time Processing**: Continuous indexing of new messages as they arrive

## Technical Architecture

### Backend Stack
- **Discord.py**: Bot framework and API integration
- **FastAPI**: REST API for message processing pipeline
- **ChromaDB**: Vector database for message storage and retrieval
- **Sentence Transformers**: Text embedding generation
- **Mistral 7B**: Local language model inference

### Data Pipeline
1. Discord message extraction with pagination handling
2. Text preprocessing and metadata extraction
3. Vector embedding generation and storage
4. RAG (Retrieval-Augmented Generation) for query processing
5. Response formatting for Discord's message constraints

### Hardware Requirements
- GPU: RTX 3090 or equivalent (tested configuration)
- RAM: 16GB+ recommended for local LLM inference
- Storage: Varies based on server message volume

## Development Timeline

The project follows a 10-week sprint plan focusing on:
- **Weeks 1-4**: Core message extraction and vector storage
- **Weeks 5-6**: LLM integration and RAG implementation  
- **Weeks 7-8**: Discord interface and query processing
- **Weeks 9-10**: Performance optimization and voice features

## Current Status

This project is in active development. Core functionality targets include reliable indexing of 50+ messages, sub-5-second query response times, and stable operation on consumer hardware.

## Installation

# Setup Instructions

1. Download & Install Ollama --> (https://ollama.com/download/windows)

2. Open up a terminal and run this command:

`ollama pull llama3.1:8b`

3. In your terminal run `pip install -r requirements.txt` from the root directory.

4. In the same terminal run: `python main.py`

5. Enjoy

## Usage

*Usage documentation will be provided upon initial release.*

## Contributing

*Contribution guidelines will be established as the project structure stabilizes.*