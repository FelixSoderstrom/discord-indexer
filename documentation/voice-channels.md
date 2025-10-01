# Voice Channels and Speech-to-Text

## Overview

The Discord-Indexer bot supports voice channel integration with real-time speech-to-text (STT) transcription. Users can interact with the bot via voice, and their speech is transcribed using local Whisper models and stored in the conversation database.

## Architecture

### Audio Pipeline Flow

```
Discord Voice Channel
    ↓
discord-ext-voice-recv (Opus packets → PCM)
    ↓
STTAudioSink (audio buffering & VAD)
    ↓
Silero VAD (speech detection)
    ↓
Audio Accumulation (48kHz buffer)
    ↓
WhisperModelManager (transcription)
    ↓
voice_transcriptions table (storage)
```

### Key Components

#### 1. STTAudioSink (`src/bot/audio_sink.py`)

Audio sink implementation that captures Discord voice packets and processes them through the STT pipeline.

**Responsibilities:**
- Receive 20ms audio packets from Discord (48kHz stereo)
- Convert to mono and resample for VAD processing
- Apply voice activity detection to filter silence
- Accumulate speech segments
- Trigger transcription when speech ends (500ms silence)
- Store transcriptions in database

**Audio Processing:**
- **Input**: 20ms PCM packets at 48kHz stereo from Discord
- **Conversion**: Stereo → Mono, 48kHz → 16kHz for VAD
- **Buffering**: Dual buffer system:
  - VAD buffer (16kHz): Accumulates until ≥512 samples for VAD processing
  - Voice-message buffer (48kHz): Accumulates speech for final transcription
- **Output**: Transcribed text stored in database

#### 2. WhisperModelManager (`src/ai/whisper_manager.py`)

Singleton manager for Whisper STT model lifecycle and transcription operations.

**Features:**
- Lazy loading with thread-safe singleton pattern
- Support for multiple Whisper model sizes (tiny to large-v3)
- GPU acceleration via CUDA (RTX 3090)
- Quantization support (int8, float16, float32)
- Async model loading to prevent blocking

**Model Configuration:**
- Default: `large-v3` (3-4GB VRAM)
- Device: `cuda` for GPU acceleration
- Compute Type: `int8` for memory efficiency

#### 3. Silero VAD Integration

Voice Activity Detection (VAD) using Silero VAD model to filter silence before transcription.

**VAD Requirements:**
- **CRITICAL**: Silero VAD requires **EXACTLY** 512, 1024, or 1536 samples at 16kHz
- Not "at least" - must be exact chunk sizes
- Default implementation uses 512 samples (32ms)

**Important**: Discord sends 20ms frames (320 samples at 16kHz after resampling). The audio sink implements buffering to:
1. Accumulate frames until ≥512 samples available
2. Extract **exactly** 512 samples for VAD processing
3. Keep remainder for next iteration

**VAD Configuration:**
- Threshold: 0.5 (speech probability)
- Minimum speech duration: 250ms
- Minimum silence duration: 500ms (configurable via `STT_SILENCE_DURATION_MS`)

### Speech Detection Flow

1. **User Silent**: Audio arrives but VAD detects no speech → discarded
2. **Speech Starts**: VAD detects speech → start accumulating audio
3. **Speech Continues**: Keep accumulating audio in voice-message buffer
4. **Silence Detected**: VAD detects silence → increment silence counter
5. **500ms Silence**: Silence threshold reached → transcribe accumulated audio
6. **Transcription**: Complete voice-message sent to Whisper → text stored

## Configuration

### Environment Variables

```env
# Whisper Model Configuration
WHISPER_MODEL=large-v3          # Model size (tiny|base|small|medium|large-v2|large-v3)
WHISPER_DEVICE=cuda             # Device (cuda|cpu)
WHISPER_COMPUTE_TYPE=int8       # Precision (int8|int8_float16|float16|float32)

# VAD Configuration
STT_SILENCE_DURATION_MS=500     # Silence duration before ending speech segment
```

### Audio Constants

Defined in `STTAudioSink.__init__`:

```python
SAMPLE_RATE_DISCORD = 48000      # Discord's native sample rate
SAMPLE_RATE_WHISPER = 16000      # Whisper's expected sample rate
FRAME_SIZE_MS = 20               # Discord sends 20ms frames
SILENCE_DURATION_MS = 500        # Configurable silence threshold
VAD_MIN_SAMPLES = 512            # Minimum samples for Silero VAD
```

## Database Schema

### voice_transcriptions Table

```sql
CREATE TABLE voice_transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    transcript_text TEXT NOT NULL,
    confidence_score REAL,
    audio_duration_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES voice_sessions(id)
);
```

**Fields:**
- `session_id`: Links to voice_sessions table
- `chunk_index`: Sequential number for transcription chunks in session
- `transcript_text`: Transcribed text content
- `confidence_score`: Average confidence (1.0 - no_speech_prob)
- `audio_duration_seconds`: Duration of audio segment
- `created_at`: Timestamp of transcription

## Usage

### Bot Voice Session

When a user requests a voice session:

1. Bot creates a private voice channel
2. Bot joins the channel with VoiceRecvClient
3. STTAudioSink is attached to capture audio
4. User joins and begins speaking
5. Speech is transcribed in real-time
6. Transcriptions are logged with `[STT]` prefix
7. Text is stored in database for DM Assistant access

### Transcription Output

Example log output:

```
[STT] User 265569842419990528 (chunk 0): Hello, can you help me with something?
[STT] User 265569842419990528 (chunk 1): I need to search for messages about deployment
```

## Performance Characteristics

### Latency

- **Target**: <500ms for real-time transcription
- **VAD buffering**: Adds 32-64ms latency for minimum chunk accumulation
- **Whisper inference**: Varies by model size and audio duration
  - large-v3: ~200-400ms for 5s audio on RTX 3090
  - medium: ~100-200ms for 5s audio

### VRAM Usage

- **Whisper large-v3 (int8)**: 3-4GB VRAM
- **Whisper medium (int8)**: 1-2GB VRAM
- **Silero VAD**: <100MB VRAM
- **Total Budget**: Must coexist with ChromaDB embeddings and Llama models on RTX 3090 (24GB)

### Audio Quality

- **Minimum voice-message duration**: 300ms (shorter segments are skipped)
- **Confidence threshold**: Segments tracked via `no_speech_prob` from Whisper
- **Buffer overflow protection**: Queue-based buffering with overflow warnings

## Error Handling

### Specific Exceptions

- `LLMProcessingError`: Whisper model failures or VAD errors
- `queue.Full`: Audio buffer overflow (packets dropped)
- `ValueError`: Audio chunk size validation errors

### Logging

All STT-related logs use the `[STT]` prefix for traceability:

```python
logger.info(f"[STT] User {user_id} (chunk {chunk_index}): {transcript_text}")
```

### Privacy Considerations

- Never log actual transcribed content in error messages
- All processing is local (no external STT APIs)
- Audio data is ephemeral (never written to disk)
- Only text transcriptions are persisted

## Troubleshooting

### "Provided number of samples is X" Error

**Cause**: Silero VAD requires **EXACTLY** 512, 1024, or 1536 samples at 16kHz. Any other size (e.g., 320, 640, 800) will be rejected.

**Solution**: The STTAudioSink now:
- Buffers incoming audio frames
- Extracts exactly 512 samples when buffer ≥512
- Keeps remainder for next VAD check
- This ensures VAD always receives exactly 512 samples

### Transcription Quality Issues

**Check:**
1. Audio duration: Very short segments (<300ms) are skipped
2. Confidence scores: Review `no_speech_prob` in segments
3. VAD sensitivity: Adjust threshold in settings if speech is cut off
4. Background noise: May affect VAD detection accuracy

### VRAM Overflow

**Symptoms**: CUDA out of memory errors during transcription

**Solutions:**
- Use smaller Whisper model (medium instead of large-v3)
- Use int8 compute type instead of float16
- Unload other models before voice sessions
- Monitor VRAM with `nvidia-smi`

## Future Enhancements

Potential improvements for voice processing:

- [ ] Real-time streaming transcription (partial results)
- [ ] Multi-speaker diarization (identify different speakers)
- [ ] Custom wake word detection
- [ ] Voice command parsing
- [ ] Noise reduction preprocessing
- [ ] Automatic language detection per user
- [ ] Transcription quality scoring and retries
- [ ] Audio caching for failed transcriptions

## References

- **Discord.py Voice**: https://discordpy.readthedocs.io/en/stable/api.html#voice-related
- **discord-ext-voice-recv**: Voice receive extension for Discord.py
- **Faster Whisper**: https://github.com/guillaumekln/faster-whisper
- **Silero VAD**: https://github.com/snakers4/silero-vad
- **Whisper Models**: https://github.com/openai/whisper

