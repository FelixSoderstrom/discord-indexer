# VLM Specialist Agent Instructions

## Key Areas of Focus
- `src/ai/model_manager.py` - Vision model lifecycle and dual model management
- `src/ai/utils.py` - Vision model operations and image description generation
- `src/ai/agents/image_analyzer.py` - ImageAnalyzer agent definition and implementation
- `src/ai/agents/sys_prompts/image_analyzer.txt` - Vision model system prompts
- `src/message_processing/image_processor.py` - Image download, validation, and processing pipeline
- `src/config/settings.py` - Vision model configuration (VISION_MODEL_NAME)

## Specific Responsibilities
### Vision Model Management
- VISION_MODEL_NAME configuration and optimization for RTX 3090
- Dual model lifecycle coordination with text models
- Vision model loading and memory management with 30-minute keep_alive
- Model availability verification and auto-download for vision models

### Image Processing Pipeline
- Discord CDN image download with async operations
- Image format validation (JPEG, PNG, GIF, BMP, WEBP support)
- Size limit enforcement (10MB maximum) and timeout handling
- Batch processing of multiple images with numbered descriptions

### ImageAnalyzer Agent Development
- Stateless agent architecture for image description generation
- System prompt engineering for structured image analysis
- Standardized output format with subject, description, details, text, and context
- Low temperature (0.1) configuration for consistent descriptions

### Vision Model Integration
- Ollama client configuration for vision model operations
- Async image description generation via generate_image_description_async
- Integration with message processing pipeline for Discord attachments
- Error handling for vision model failures and graceful degradation

### Structured Image Analysis
- Subject identification and main visual element extraction
- Scene description generation (2-3 sentences)
- Notable detail extraction (2-3 bullet points)
- Visible text detection and extraction
- Context and environment type classification

## Coordination Boundaries
- **Works WITH message-processor**: Provides image descriptions for embedding storage
- **Works WITH model-manager**: Coordinates vision model lifecycle with text models
- **Does NOT**: Handle text model operations or LLM agent management
- **Does NOT**: Implement message processing pipeline logic beyond image handling

## Implementation Process
1. **Analysis Phase**: Examine vision model requirements and image processing needs
2. **Planning Phase**: Design image processing pipeline and vision model integration
3. **Implementation Phase**: Build ImageAnalyzer agent and image processing components
4. **Testing Phase**: Test vision model operations with realistic Discord image data
5. **Optimization Phase**: Tune for RTX 3090 hardware specs and response quality

## Testing Approach
- Create test scripts for vision model health checks and loading
- Test image download and validation with various formats
- Test ImageAnalyzer agent with sample Discord image attachments
- Validate structured output format consistency
- Focus on dual model coordination and memory management
- Test error handling for unsupported formats and download failures

## Vision Model Architecture
- **Model Loading**: Vision model loaded first in dual model system with 30m keep_alive
- **Processing Pattern**: Async image processing via generate_image_description_async
- **Output Format**: Structured template with standardized fields
- **Error Recovery**: Graceful handling with meaningful error messages
- **Performance Targets**: Sub-5-second image processing on RTX 3090 + 16GB RAM