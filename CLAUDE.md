TODAYS DATE: 20 SEPTEMBER 2025

# Discord-Indexer - Claude Code Configuration

## Project Overview
Discord bot that indexes server message history and provides intelligent search through DMs using local LLM processing. Built with Discord.py, ChromaDB, and Mistral 7B.

## Core Technologies
- **Primary Language**: Python 3.10.6
- **Bot Framework**: Discord.py 2.6.0
- **Database**: ChromaDB 1.0.20
- **LLM**: Local Llama 8B via Ollama

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
- IMPORTANT: **ALWAYS** read relevant documentation for the task you are working on **before** implementing changes.
- IMPORTANT: **ALWAYS** update relevant documentation after changes have been made to a feature.

### Error Handling Guidelines
- **NEVER catch broad exceptions** (`Exception as e` is prohibited)
- Catch **specific exceptions only**
- **Always log errors** using the logger

### Security Considerations
- Never log or expose Discord tokens
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