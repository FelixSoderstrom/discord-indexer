# Bug Analysis - STT Real-Time Transcription Failure

## Problem Statement

Transcription only occurs when user LEAVES voice channel, not when natural speech pauses end (VAD silence detection threshold reached).

## Expected Flow

```
1. User speaks → VAD detects speech → start accumulating audio
2. User stops speaking → VAD detects silence → increment silence_counter
3. silence_counter >= SILENCE_FRAMES (25 frames = 500ms) → _transcribe_segment() called
4. Audio transcribed → logged → stored in DB
5. State reset, ready for next speech segment
```

## Actual Flow (Suspected)

```
1. User speaks → VAD detects speech → start accumulating audio
2. User stops speaking → ??? silence_counter not incrementing properly ???
3. silence_counter never reaches threshold → _transcribe_segment() NOT called
4. User leaves channel → cleanup() called → final flush transcribes ALL audio at once
```

## Key Calculations

### Silence Threshold
- `SILENCE_DURATION_MS = 500ms` (from settings)
- `FRAME_SIZE_MS = 20ms` (Discord packet size)
- `SILENCE_FRAMES = 500 / 20 = 25 frames`

### VAD Processing Rate
- Discord: 20ms frames at 48kHz = 960 samples/frame
- After resampling to 16kHz: 320 samples/frame
- VAD requires: exactly 512 samples at 16kHz
- **VAD decision made every: ~40ms (every 2 Discord frames)**

### Effective Silence Duration
If silence_counter increments once per VAD decision:
- 25 increments × 40ms = **1000ms actual threshold**
- NOT the intended 500ms!

## Hypothesis

**Root Cause:** Mismatch between SILENCE_FRAMES calculation and VAD decision frequency.

`SILENCE_FRAMES` is calculated assuming silence counter increments every 20ms (per Discord frame), but VAD decisions (and thus silence counter increments) only happen every ~40ms (when 512 samples accumulated).

This means:
1. Intended silence threshold: 500ms
2. Actual silence threshold: ~1000ms
3. Users might resume speaking before reaching actual threshold
4. Result: transcription never triggers during natural pauses

## Code Locations

### Silence Threshold Calculation
`src/bot/audio_sink.py:104`
```python
self.SILENCE_FRAMES = int(self.SILENCE_DURATION_MS / self.FRAME_SIZE_MS)  # 500/20 = 25
```

### Silence Counter Increment
`src/bot/audio_sink.py:314`
```python
vad_state['silence_counter'] += 1  # Only when vad_decision_made == True
```

### Transcription Trigger
`src/bot/audio_sink.py:323-331`
```python
if vad_state['silence_counter'] >= self.SILENCE_FRAMES:
    self._transcribe_segment(user_id, accumulated_audio)
```

### VAD Decision Frequency
`src/bot/audio_sink.py:276-286`
```python
if len(buffered_audio) >= self.VAD_MIN_SAMPLES:  # 512 samples at 16kHz
    vad_chunk = buffered_audio[:self.VAD_MIN_SAMPLES]
    is_speech = self._apply_vad(vad_chunk)
    vad_decision_made = True
```

## Proposed Fix

### Option 1: Adjust SILENCE_FRAMES Calculation
Account for VAD processing rate in threshold calculation:

```python
# Each VAD decision covers ~40ms (2 Discord frames worth of audio)
VAD_DECISION_INTERVAL_MS = (self.VAD_MIN_SAMPLES / 16000) * 1000  # 32ms
self.SILENCE_FRAMES = int(self.SILENCE_DURATION_MS / VAD_DECISION_INTERVAL_MS)
```

This would give: `500ms / 32ms = 15-16 VAD decisions` instead of 25 frame counts.

### Option 2: Increment Counter Per Frame, Not Per VAD Decision
Track silence at Discord frame rate (20ms), not VAD decision rate (40ms):

```python
# When no VAD decision made yet (buffering):
if not vad_decision_made and vad_state['is_speaking']:
    # Assume continued speech/silence based on previous state
    # But this requires tracking frames vs VAD decisions differently
```

### Option 3: Use Time-Based Threshold Instead of Frame Count
Track actual time elapsed since last speech:

```python
if is_speech:
    vad_state['last_speech_time'] = time.time()
elif vad_state['is_speaking']:
    silence_duration = time.time() - vad_state['last_speech_time']
    if silence_duration >= (self.SILENCE_DURATION_MS / 1000):
        self._transcribe_segment(user_id, accumulated_audio)
```

## Testing Requirements

1. **Enable debug logging** to verify:
   - VAD decision frequency
   - Silence counter increments
   - Transcription trigger attempts

2. **Test scenarios:**
   - Short utterance (1-2 seconds) + long pause (>1 second)
   - Continuous speech with 500ms pauses
   - Back-to-back sentences with natural pauses

3. **Expected logs for working system:**
   ```
   [STT-VAD] User X: Speech detected
   [STT-VAD] User X: Silence frame 1/15
   [STT-VAD] User X: Silence frame 15/15
   [STT-VAD] User X: Silence threshold reached, triggering transcription
   [STT] User X (chunk 0): {transcribed text}
   ```

## Recommendation

**Implement Option 3 (time-based threshold)** for most robust solution. It's independent of frame rates and VAD decision timing.
