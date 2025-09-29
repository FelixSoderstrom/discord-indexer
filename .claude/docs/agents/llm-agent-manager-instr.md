# LLM Agent Manager Instructions

## Key Areas of Focus
- `src/ai/utils.py` - Ollama client and model management utilities
- `src/ai/chat_completion.py` - Pure LLM API interface with async support
- `src/ai/model_manager.py` - Dual model lifecycle management (text + vision)
- `src/ai/agents/dm_assistant.py` - Native Ollama tool calling DM assistant
- `src/ai/agents/langchain_dm_assistant.py` - LangChain-based DM assistant
- `src/ai/agents/link_analyzer.py` - Content extraction agent
- `src/ai/agents/image_analyzer.py` - Vision model image analysis agent
- `src/ai/agents/sys_prompts/` - System prompts for all agents
- `src/ai/agents/tools/langchain_search_tool.py` - LangChain vector database search
- `src/ai/agents/tools/search_tool.py` - Core search tool implementation

## Specific Responsibilities
### Ollama Configuration & Management
- Dual model system: TEXT_MODEL_NAME (e.g., llama3.2:3b) + VISION_MODEL_NAME (e.g., minicpm-v)
- ModelManager handles simultaneous loading with 30m keep-alive
- Advanced model utilities: context window detection, memory management, health checking
- Performance optimization for consumer hardware (RTX 3090, 16GB RAM)
- Model unloading and memory efficiency controls

### Agent Definition Management
- Dual DM Assistant implementations: Native Ollama tool calling + LangChain
- LinkAnalyzer for HTML content extraction and processing
- ImageAnalyzer for vision model-based image description
- Server-specific agent creation and caching
- Tool integration with both native Ollama and LangChain frameworks
- Agent workflow optimization and response formatting

### System Prompt Engineering
- System prompt design and optimization
- Context-aware prompt generation
- Prompt template management and versioning
- Response quality optimization through prompt tuning

### RAG Implementation
- ChromaDB vector database search integration
- Server-specific search tool binding and caching
- LangChain tool decorator wrapper for seamless agent integration
- Native Ollama tool calling schema definition and execution
- Context synthesis and relevance scoring
- Query processing with configurable result limits

### Search Tool Management
- Dual search tool architecture: Core implementation + LangChain wrapper
- Server-bound search tools with automatic context isolation
- Search result formatting and ranking optimization
- Support for both native Ollama and LangChain tool calling patterns
- Dynamic search tool creation and server-specific binding

## Coordination Boundaries
- **Works WITH message-processor**: Provides content extraction for links and images
- **Works WITH queue-manager**: Receives processed user messages and context
- **Works WITH db components**: Uses ChromaDB for vector search and message retrieval
- **Provides TO other components**: ModelManager for shared model access
- **Does NOT**: Handle message processing pipeline logic
- **Does NOT**: Implement queue system operations
- **Does NOT**: Manage Discord API interactions directly

## Implementation Process
1. **Analysis Phase**: Examine dual model requirements and agent performance
2. **Planning Phase**: Design agent architecture with ModelManager integration
3. **Implementation Phase**: Build agents with both native Ollama and LangChain support
4. **Testing Phase**: Test model simultaneous loading, agent responses, and tool calling
5. **Optimization Phase**: Tune for hardware specs, memory efficiency, and response quality
6. **Integration Phase**: Ensure proper coordination with message processing and queue systems

## Testing Approach
- Create test scripts for ModelManager dual model loading
- Test both native Ollama and LangChain agent implementations
- Validate server-specific search tool binding and isolation
- Test vision model integration with ImageAnalyzer
- Validate RAG performance with ChromaDB integration
- Test system prompts with various scenarios and model combinations
- Test model health checking and memory management
- Focus on consumer hardware optimization (RTX 3090, 16GB RAM)
- Test tool calling with both frameworks (native + LangChain)
- Validate async operations and timeout handling

## New Features & Components (Added Since Original Instructions)

### ModelManager (src/ai/model_manager.py)
- Centralized dual model lifecycle management
- Simultaneous loading of text and vision models with keep-alive
- Health checking for both models with timing metrics
- Proper error handling and initialization validation
- Shared model access for all agent components

### ImageAnalyzer (src/ai/agents/image_analyzer.py)
- Vision model-based image description and analysis
- Structured output format with subject, description, details, text, and context
- Integration with ModelManager for vision model access
- Async processing with proper error handling and validation

### Native Ollama Tool Calling (DMAssistant)
- Direct Ollama tool calling without LangChain overhead
- Tool schema definition and execution within Ollama chat API
- Stateless conversation management with tool integration
- Server-specific search tool binding and execution

### Advanced Model Utilities
- Context window detection and caching for optimal token usage
- Model loading status checking and memory management
- Model unloading capabilities for memory efficiency
- Special handling for model-specific quirks (e.g., mistral-nemo context correction)

### Enhanced Configuration Management
- Pydantic-based settings with environment variable validation
- Dual model configuration with TEXT_MODEL_NAME and VISION_MODEL_NAME
- LangChain verbosity controls and debugging support
- Backward compatibility properties for legacy configurations

### Async Operation Support
- Full async support across all agent operations
- Proper timeout handling and error recovery
- Thread pool execution for blocking operations
- Async health checking with configurable timeouts

## Current Model Recommendations
- **Text Model**: llama3.2:3b (lightweight, efficient for conversation)
- **Vision Model**: minicpm-v (optimized for image analysis)
- **Alternative Text**: llama3.1:8b (higher quality, more memory)
- **Alternative Vision**: llama3.2-vision:11b (higher quality vision processing)