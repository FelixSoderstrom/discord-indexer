# CRITICAL BUG - STT Real-Time Transcription

## Bug Description

**Severity**: CRITICAL
**Status**: UNRESOLVED
**Discovered**: 2025-10-01

### Issue

Transcription does not happen in real-time during voice sessions. Audio is only transcribed when the user LEAVES the voice channel, not when speech ends naturally during the session.

### Expected Behavior

1. User speaks in voice channel
2. Speech ends (500ms silence detected by VAD)
3. Accumulated audio is immediately transcribed
4. Transcription stored in database
5. Log shows `[STT] User {user_id} (chunk X): {text}`

### Actual Behavior

1. User speaks in voice channel
2. Speech ends (500ms silence detected by VAD)
3. **Nothing happens** - no transcription triggered
4. User leaves channel
5. **Only then** does transcription occur during cleanup

### Root Cause

The VAD silence detection logic fails to properly signal when speech segments are complete. The silence counter reaches the threshold but does not trigger the `_transcribe_segment()` call during active processing.

### Impact

- No real-time transcription during voice sessions
- Defeats the purpose of STT integration
- Users cannot see their speech being transcribed live
- DM Assistant cannot access transcriptions until user leaves channel

### Affected Components

- `src/bot/audio_sink.py` - `STTAudioSink.process_user_audio()` method
- VAD state machine logic around lines 304-337
- Silence detection and transcription trigger

### Investigation Notes

The processing thread runs continuously, VAD is loaded and processing audio, but the transcription is only triggered in the cleanup phase when `self._processing = False` and remaining audio is flushed.

### Must Fix Before

Phase 3 (TTS Integration) cannot proceed until real-time STT works properly.

---

**Phase 2 STT Implementation completed but BLOCKED by this bug**
