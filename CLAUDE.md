TODAYS DATE: OCTOBER 1 2025

# Discord-Indexer

## Project Overview
Discord bot that indexes server message history and provides intelligent search through DMs using local LLM processing. Built with Discord.py, ChromaDB, and Llama 3.2.

## Core Technologies
- **Primary Language**: Python 3.10.6
- **Bot Framework**: Discord.py 2.6.0
- **Database**: ChromaDB 1.0.20
- **LLM**: Llama 3B via Ollama
- **VLM**: MiniCPM-v
- **Text embedding model**: BAAI/bge-large-en-v1.5
- **Speech to text**: Whisper

## Universal Standards (ALL Agents)

### Code Quality Standards
- Follow **Zen of Python** principles strictly
- Use **Google Docstring** format for documentation
- Apply **type annotations** using the Typing library
- **ALWAYS** import at top of file - **NEVER** import inside conditionals.
- **ALWAYS use absolute imports** - Never use relative imports
  - Correct: `from src.db.conversation_db import get_conversation_db`
  - Incorrect: `from ...db.conversation_db import get_conversation_db`

### Documentation
- Feature-level documentation is available in `documentation/[feature].md`
- Agent-specific instructions are available in `.claude/docs/agents/[agent-name]-instr.md`
- IMPORTANT: **ALWAYS** update relevant documentation **and** instructions after changes have been made to a feature.

### Error Handling Guidelines
- **NEVER catch broad exceptions** (`Exception as e` is prohibited)
- Catch **specific exceptions only**
- **Always log errors** using the logger

### Security Considerations
- Never log or expose sensitive data
- Secure handling of message data
- Local-only LLM processing (no external API calls)

### Performance Targets
- Index 50+ messages reliably
- Sub-5-second query response times
- Stable operation on consumer hardware (RTX 3090, 24GB RAM)

## Notes for All Agents
- Never commit changes unless explicitly asked to do so
- Use specific exception handling patterns
- Never catch broad exceptions (`Exception as e:`)
- Maintain separation of concerns across modules
- **Always** activate venv when using the terminal
- **NO** emojis in the codebase!