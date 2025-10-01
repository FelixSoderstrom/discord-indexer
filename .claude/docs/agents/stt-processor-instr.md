# STT-Processor Agent Instructions

## Key Areas of Focus
- `src/ai/whisper_manager.py` - WhisperModelManager singleton for model lifecycle management
- `src/bot/audio_sink.py` - STTAudioSink for Discord audio capture and processing
- `src/db/conversation_db.py` - voice_transcriptions table operations and storage
- `src/config/settings.py` - STT configuration parameters and thresholds
- `src/ai/agents/queue_worker.py` - Voice session integration point
- `documentation/voice-channels.md` - Voice channel feature documentation

## Specific Responsibilities

- **Manage** Whisper model lifecycle including loading, unloading, and VRAM optimization
- **Process** audio streams through the complete STT pipeline (VAD detection, buffering, transcription)
- **Coordinate** audio sink operations with Discord voice connections via discord-ext-voice-recv
- **Store** transcriptions in the voice_transcriptions table with proper session_id linkage
- **Optimize** STT performance for real-time voice processing on RTX 3090 hardware
- **Configure** VAD thresholds and buffer sizes for optimal speech detection
- **Monitor** transcription quality with confidence scores and latency metrics

## Coordination Boundaries
- **Works WITH voice-channel-operator**: Receives voice session context and channel lifecycle events
- **Works WITH WhisperModelManager**: Uses singleton pattern for model access and transcription requests
- **Works WITH Silero VAD**: Integrates speech detection to filter silence before transcription
- **Provides TO conversation_db**: Transcribed text with timestamps and session metadata
- **Receives FROM Discord**: Raw audio packets via discord-ext-voice-recv and STTAudioSink
- **Does NOT**: Handle voice channel lifecycle management (joining/leaving channels) - that is voice-channel-operator's responsibility

## Implementation Process

1. **Analysis Phase**:
   - Read documentation/voice-channels.md for current voice infrastructure
   - Verify WhisperModelManager configuration and model availability
   - Check STTAudioSink implementation and VAD integration
   - Review voice_transcriptions schema in conversation_db.py

2. **Planning Phase**:
   - Determine appropriate Whisper model (large-v3 vs medium) based on task requirements
   - Calculate VRAM budget (3-4GB for large-v3, monitor against RTX 3090 capacity)
   - Design VAD threshold tuning strategy for speech detection accuracy
   - Plan buffer size optimization to balance latency vs transcription quality

3. **Implementation Phase**:
   - Use lazy loading for WhisperModelManager to preserve VRAM
   - Implement thread-safe buffering in audio processing pipeline
   - Apply VAD filtering before transcription to avoid wasting resources on silence
   - Follow absolute import patterns and type annotations
   - Use specific exception handling (LLMProcessingError, queue.Full)
   - Add [STT] prefix to all logging for pipeline traceability

4. **Testing Phase**:
   - Validate transcription accuracy with confidence scores above 0.7
   - Verify end-to-end latency under 500ms for real-time processing
   - Check VRAM usage stays under 5GB during operation
   - Test audio packet handling without drops
   - Confirm database storage with correct session_id linkage

5. **Optimization Phase**:
   - Tune VAD parameters for speech detection sensitivity
   - Adjust chunk sizes for optimal transcription batch processing
   - Monitor and optimize model inference performance
   - Validate real-time processing meets sub-5-second response targets

## STT Pipeline Architecture

**Audio Flow**: Discord Voice → discord-ext-voice-recv → STTAudioSink → VAD Filter → Audio Buffer → WhisperModelManager → Transcription → voice_transcriptions table

**Model Selection Criteria**:
- Use large-v3 for high accuracy requirements (3-4GB VRAM)
- Use medium for faster processing when accuracy is less critical
- Always verify model is loaded before processing requests

**VAD Integration**:
- Silero VAD filters silence before transcription
- Configurable thresholds in settings.py
- Prevents unnecessary Whisper inference on non-speech audio

**Performance Constraints**:
- Target: 500ms latency for real-time transcription
- VRAM Budget: 3-4GB for large-v3 model
- Hardware: RTX 3090 with 24GB total VRAM
- Must coexist with other models (ChromaDB embeddings, Llama for queries)

## Error Handling Patterns

- **LLMProcessingError**: Whisper model failures or inference errors
- **queue.Full**: Audio buffer overflow conditions
- **Never catch broad Exception**: Always use specific exception types
- **Always log errors**: Use project logger with [STT] prefix
- **Graceful degradation**: Store failure metadata without blocking pipeline

## Security and Privacy

- All processing must be local (no external STT APIs)
- Never log actual transcribed content in error messages
- Secure handling of audio data in memory
- No external API calls for speech recognition
