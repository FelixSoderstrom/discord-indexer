"""AudioSink implementation for capturing and transcribing Discord voice audio.

This module provides an AudioSink implementation using discord-ext-voice-recv
that captures Opus packets from Discord voice channels, applies voice activity
detection (VAD), and transcribes speech using Whisper STT.
"""

import asyncio
import io
import logging
import queue
import threading
import time
from typing import Dict, Optional, Any

import discord
import numpy as np
import torch
from discord.ext import voice_recv

from src.ai.whisper_manager import get_whisper_manager
from src.db.conversation_db import get_conversation_db
from src.config.settings import settings
from src.exceptions.message_processing import LLMProcessingError


logger = logging.getLogger(__name__)


class STTAudioSink(voice_recv.AudioSink):
    """AudioSink for capturing and transcribing Discord voice audio.

    Inherits from discord.ext.voice_recv.AudioSink to receive audio packets
    from Discord voice channels. Implements voice activity detection (VAD)
    using Silero VAD and transcribes speech using Whisper STT.

    Audio Processing Flow:
        1. Receive 20ms Opus packets from Discord (48kHz stereo)
        2. Decode Opus to PCM
        3. Buffer audio per user in thread-safe queue
        4. Apply Silero VAD to detect speech activity
        5. Accumulate speech until 500ms silence detected
        6. Resample from 48kHz to 16kHz for Whisper
        7. Transcribe using WhisperModelManager
        8. Store transcription in conversation database
    """

    def __init__(
        self,
        session_id: int,
        channel_id: int,
        db_instance: Optional[Any] = None,
        whisper_manager: Optional[Any] = None
    ):
        """Initialize STT AudioSink.

        Args:
            session_id: Database session ID for tracking voice session
            channel_id: Discord voice channel ID
            db_instance: ConversationDatabase instance (optional, uses singleton if None)
            whisper_manager: WhisperModelManager instance (optional, uses singleton if None)
        """
        super().__init__()

        self.session_id = session_id
        self.channel_id = channel_id

        # Database and model managers
        self.db = db_instance or get_conversation_db()
        self.whisper = whisper_manager or get_whisper_manager()

        # Per-user audio buffers (thread-safe queues)
        self._user_buffers: Dict[int, queue.Queue] = {}
        self._user_locks: Dict[int, threading.Lock] = {}

        # VAD state tracking per user
        self._user_vad_state: Dict[int, Dict[str, Any]] = {}
        
        # VAD buffering per user (accumulate samples before VAD processing)
        self._vad_buffers: Dict[int, list] = {}

        # Transcription chunk tracking
        self._chunk_counters: Dict[int, int] = {}

        # Processing control
        self._processing = True
        self._processing_tasks: Dict[int, asyncio.Task] = {}
        self._processing_threads: Dict[int, threading.Thread] = {}
        self._shutdown_event = threading.Event()

        # VAD model (shared across users)
        self._vad_model: Optional[torch.nn.Module] = None
        self._vad_utils = None

        # Track first packet received per user for debug logging
        self._first_packet_received: Dict[int, bool] = {}

        # Audio constants
        self.SAMPLE_RATE_DISCORD = 48000  # Discord's sample rate
        self.SAMPLE_RATE_WHISPER = 16000  # Whisper's expected sample rate
        self.FRAME_SIZE_MS = 20  # Discord sends 20ms frames
        self.SAMPLES_PER_FRAME = int(self.SAMPLE_RATE_DISCORD * self.FRAME_SIZE_MS / 1000)
        self.SILENCE_DURATION_MS = settings.STT_SILENCE_DURATION_MS
        self.SILENCE_FRAMES = int(self.SILENCE_DURATION_MS / self.FRAME_SIZE_MS)
        
        # VAD constants (Silero VAD requires minimum 512 samples at 16kHz)
        self.VAD_MIN_SAMPLES = 512  # 32ms at 16kHz minimum for Silero VAD

        logger.info(
            f"Initialized STTAudioSink for session {session_id}, "
            f"channel {channel_id}"
        )

    def wants_opus(self) -> bool:
        """Specify whether we want raw Opus packets or decoded PCM.

        Returns:
            False - We want decoded PCM audio for VAD and transcription
        """
        return False

    def _ensure_vad_loaded(self) -> None:
        """Ensure Silero VAD model is loaded (lazy loading).

        Raises:
            LLMProcessingError: If VAD model loading fails
        """
        if self._vad_model is None:
            try:
                logger.debug("Loading Silero VAD model for AudioSink")

                # Load Silero VAD from torch hub
                self._vad_model, vad_utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )

                # Extract utility functions
                self._get_speech_timestamps = vad_utils[0]

                logger.info("Successfully loaded Silero VAD model for AudioSink")

            except Exception as e:
                logger.error(f"Failed to load Silero VAD model: {e}")
                raise LLMProcessingError(f"Could not load Silero VAD model: {e}")

    def write(self, user: discord.User, data: voice_recv.VoiceData) -> None:
        """Receive audio packet from Discord (called by discord.py).

        This method is called by discord.py for each 20ms audio packet received
        from a user in the voice channel. Audio is buffered per-user for processing.

        Args:
            user: Discord user who sent the audio
            data: VoiceData object containing decoded PCM audio
        """
        if not self._processing:
            logger.debug(f"Ignoring audio packet from user {user.id} - processing stopped")
            return

        user_id = user.id

        # Log first packet received for this user
        if user_id not in self._first_packet_received:
            logger.info(f"[STT] First audio packet received from user {user_id}")
            self._first_packet_received[user_id] = True
        else:
            logger.debug(f"Received audio packet from user {user_id}")

        # Initialize user buffer if needed
        if user_id not in self._user_buffers:
            self._user_buffers[user_id] = queue.Queue()
            self._user_locks[user_id] = threading.Lock()
            self._chunk_counters[user_id] = 0
            self._user_vad_state[user_id] = {
                'speech_frames': [],
                'silence_counter': 0,
                'is_speaking': False
            }
            self._vad_buffers[user_id] = []  # Initialize VAD buffer for this user

            logger.debug(f"Initialized audio buffer for user {user_id}")

            # Start processing thread for this user
            self.start_processing(user_id)

        # Extract PCM data from VoiceData
        # discord-ext-voice-recv provides decoded PCM as bytes
        pcm_data = data.pcm

        # Put audio data in user's queue
        try:
            self._user_buffers[user_id].put_nowait({
                'pcm': pcm_data,
                'timestamp': time.time()
            })
        except queue.Full:
            logger.warning(f"Audio buffer full for user {user_id}, dropping packet")

    def process_user_audio(self, user_id: int, audio_buffer: queue.Queue) -> None:
        """Process buffered audio for a user (VAD + transcription).

        This method runs in a background thread to process audio packets
        from the user's buffer. It applies VAD to detect speech activity
        and triggers transcription when speech segments are complete.

        Args:
            user_id: Discord user ID
            audio_buffer: Thread-safe queue containing audio packets
        """
        try:
            logger.info(f"[THREAD] Starting for user {user_id}")
            logger.debug(f"Started audio processing thread for user {user_id}")

            # Ensure VAD is loaded
            try:
                self._ensure_vad_loaded()
            except LLMProcessingError as e:
                logger.error(f"Cannot process audio without VAD: {e}")
                return

            logger.info(f"[THREAD] VAD loaded for user {user_id}")

            accumulated_audio = []
            loop_iterations = 0

            logger.info(f"[THREAD] Entering loop for user {user_id}")
            while self._processing or not audio_buffer.empty():
                loop_iterations += 1
                if loop_iterations == 1:
                    logger.info(f"[THREAD] First loop iteration for user {user_id}")
                elif loop_iterations % 100 == 0:  # Log every 100 iterations (~2 seconds)
                    logger.info(f"[THREAD] Loop still running for user {user_id}, iteration {loop_iterations}")
                try:
                    # Get audio packet with timeout
                    packet = audio_buffer.get(timeout=0.1)
                    pcm_data = packet['pcm']

                    # Convert PCM bytes to numpy array (int16)
                    audio_array = np.frombuffer(pcm_data, dtype=np.int16)

                    # Discord sends stereo, convert to mono for VAD
                    if len(audio_array) % 2 == 0:
                        # Average left and right channels
                        audio_mono = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
                    else:
                        audio_mono = audio_array

                    # Convert to float32 for VAD (range -1 to 1)
                    audio_float = audio_mono.astype(np.float32) / 32768.0

                    # Resample to 16kHz for VAD
                    audio_16k = self._resample_audio(audio_float, self.SAMPLE_RATE_DISCORD, 16000)

                    # Safety check: Verify user still exists in dictionaries before accessing
                    if user_id not in self._vad_buffers:
                        logger.warning(f"User {user_id} removed from buffers during processing")
                        break
                    if user_id not in self._user_vad_state:
                        logger.warning(f"User {user_id} removed from VAD state during processing")
                        break

                    # Buffer 16kHz audio for VAD (Silero requires EXACTLY 512/1024/1536 samples)
                    self._vad_buffers[user_id].append(audio_16k)

                    # Concatenate all buffered audio
                    buffered_audio = np.concatenate(self._vad_buffers[user_id])

                    # Apply VAD only when we have enough samples (extract exactly 512)
                    vad_state = self._user_vad_state[user_id]
                    vad_decision_made = False
                    is_speech = False

                    if len(buffered_audio) >= self.VAD_MIN_SAMPLES:
                        # Extract exactly 512 samples for VAD
                        vad_chunk = buffered_audio[:self.VAD_MIN_SAMPLES]

                        # Keep remaining samples for next iteration
                        remainder = buffered_audio[self.VAD_MIN_SAMPLES:]
                        self._vad_buffers[user_id] = [remainder] if len(remainder) > 0 else []

                        # Apply VAD to exact chunk size
                        is_speech = self._apply_vad(vad_chunk)
                        vad_decision_made = True

                        logger.debug(
                            f"[STT-VAD] User {user_id}: VAD decision = {is_speech}, "
                            f"was_speaking = {vad_state['is_speaking']}, "
                            f"silence_counter = {vad_state['silence_counter']}"
                        )
                    else:
                        # Not enough samples yet, keep buffering
                        # Continue with previous speaking state until we can make a VAD decision
                        self._vad_buffers[user_id] = [buffered_audio]
                        logger.debug(
                            f"[STT-VAD] User {user_id}: Buffering for VAD "
                            f"({len(buffered_audio)}/{self.VAD_MIN_SAMPLES} samples), "
                            f"maintaining is_speaking = {vad_state['is_speaking']}"
                        )

                    # Process VAD decision
                    if vad_decision_made:
                        if is_speech:
                            # Speech detected
                            vad_state['is_speaking'] = True
                            vad_state['silence_counter'] = 0
                            accumulated_audio.append(audio_float)
                            logger.debug(f"[STT-VAD] User {user_id}: Speech detected, accumulating audio")

                        elif vad_state['is_speaking']:
                            # Was speaking, now silence detected
                            vad_state['silence_counter'] += 1
                            accumulated_audio.append(audio_float)

                            logger.debug(
                                f"[STT-VAD] User {user_id}: Silence frame "
                                f"{vad_state['silence_counter']}/{self.SILENCE_FRAMES}"
                            )

                            # Check if silence threshold reached
                            if vad_state['silence_counter'] >= self.SILENCE_FRAMES:
                                # End of speech segment, trigger transcription
                                if accumulated_audio:
                                    logger.info(
                                        f"[STT-VAD] User {user_id}: Silence threshold reached, "
                                        f"triggering transcription"
                                    )
                                    self._transcribe_segment(user_id, accumulated_audio)
                                    accumulated_audio = []

                                vad_state['is_speaking'] = False
                                vad_state['silence_counter'] = 0
                        else:
                            # Not speaking and no speech detected - discard audio
                            logger.debug(f"[STT-VAD] User {user_id}: No speech, discarding audio")
                    else:
                        # No VAD decision made yet (buffering), continue accumulating if already speaking
                        if vad_state['is_speaking']:
                            accumulated_audio.append(audio_float)
                            logger.debug(
                                f"[STT-VAD] User {user_id}: Still speaking (buffering phase), "
                                f"accumulating audio"
                            )

                except queue.Empty:
                    # No audio packets, check if we should flush
                    if accumulated_audio and not self._processing:
                        self._transcribe_segment(user_id, accumulated_audio)
                        accumulated_audio = []
                    continue

                except Exception as e:
                    logger.error(
                        f"Error processing audio for user {user_id}: {e}",
                        exc_info=True
                    )

            # Final flush of any remaining audio
            if accumulated_audio:
                self._transcribe_segment(user_id, accumulated_audio)

            logger.debug(f"Audio processing thread ended for user {user_id}")
        except Exception as e:
            logger.error(f"[THREAD] Crashed for user {user_id}: {e}", exc_info=True)

    def _resample_audio(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int
    ) -> np.ndarray:
        """Resample audio to target sample rate.

        Args:
            audio: Audio data as numpy array
            orig_sr: Original sample rate
            target_sr: Target sample rate

        Returns:
            Resampled audio array
        """
        if orig_sr == target_sr:
            return audio

        # Simple linear interpolation resampling
        # For production, consider using scipy.signal.resample or librosa
        duration = len(audio) / orig_sr
        target_length = int(duration * target_sr)

        indices = np.linspace(0, len(audio) - 1, target_length)
        resampled = np.interp(indices, np.arange(len(audio)), audio)

        return resampled.astype(np.float32)

    def _apply_vad(self, audio: np.ndarray) -> bool:
        """Apply Silero VAD to detect speech in audio frame.

        Args:
            audio: Audio data as numpy array (16kHz, mono, float32)

        Returns:
            True if speech detected, False otherwise
        """
        try:
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio)

            # Get speech probability
            speech_prob = self._vad_model(audio_tensor, 16000).item()

            # Threshold for speech detection
            return speech_prob > 0.5

        except Exception as e:
            logger.error(f"VAD processing error: {e}")
            return False

    def _transcribe_segment(self, user_id: int, audio_frames: list) -> None:
        """Transcribe accumulated audio segment.

        Args:
            user_id: Discord user ID
            audio_frames: List of audio frames (numpy arrays)
        """
        try:
            # Concatenate all frames
            full_audio = np.concatenate(audio_frames)

            # Resample to 16kHz for Whisper
            audio_16k = self._resample_audio(
                full_audio,
                self.SAMPLE_RATE_DISCORD,
                self.SAMPLE_RATE_WHISPER
            )

            # Calculate duration
            duration_seconds = len(full_audio) / self.SAMPLE_RATE_DISCORD

            # Skip very short segments
            if duration_seconds < 0.3:
                logger.debug(
                    f"Skipping very short audio segment ({duration_seconds:.2f}s) "
                    f"for user {user_id}"
                )
                return

            logger.debug(
                f"Transcribing {duration_seconds:.2f}s audio segment "
                f"for user {user_id}"
            )

            # Transcribe using Whisper
            result = self.whisper.transcribe_buffer(
                audio_data=audio_16k,
                sample_rate=self.SAMPLE_RATE_WHISPER,
                language=None,  # Auto-detect
                task="transcribe"
            )

            transcript_text = result.get('text', '').strip()

            if not transcript_text:
                logger.debug(f"No transcription produced for user {user_id}")
                return

            # Calculate average confidence from segments
            segments = result.get('segments', [])
            avg_confidence = None
            if segments:
                confidences = [
                    1.0 - seg.get('no_speech_prob', 0.5)
                    for seg in segments
                ]
                avg_confidence = sum(confidences) / len(confidences) if confidences else None

            # Get chunk index
            chunk_index = self._chunk_counters[user_id]
            self._chunk_counters[user_id] += 1

            # Store in database
            success = self.db.add_transcription(
                session_id=self.session_id,
                chunk_index=chunk_index,
                transcript_text=transcript_text,
                confidence_score=avg_confidence,
                audio_duration_seconds=duration_seconds
            )

            if success:
                logger.info(
                    f"[STT] User {user_id} (chunk {chunk_index}): {transcript_text}"
                )
            else:
                logger.warning(
                    f"Failed to store transcription for user {user_id}, "
                    f"chunk {chunk_index}"
                )

        except LLMProcessingError as e:
            logger.error(f"Transcription failed for user {user_id}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error transcribing audio for user {user_id}: {e}",
                exc_info=True
            )

    def start_processing(self, user_id: int) -> None:
        """Start audio processing thread for a user.

        Args:
            user_id: Discord user ID
        """
        if user_id not in self._user_buffers:
            logger.warning(f"No audio buffer exists for user {user_id}")
            return

        # Start processing thread
        processing_thread = threading.Thread(
            target=self.process_user_audio,
            args=(user_id, self._user_buffers[user_id]),
            daemon=False,  # Non-daemon so we can properly join threads
            name=f"AudioProcessor-{user_id}"
        )
        processing_thread.start()

        # Track thread reference for cleanup
        self._processing_threads[user_id] = processing_thread

        logger.debug(f"Started audio processing thread for user {user_id}")

    def cleanup(self) -> None:
        """Cleanup audio sink resources and finalize processing.

        This method should be called when the audio sink is no longer needed
        (e.g., when bot leaves voice channel). It processes any remaining
        audio and releases resources.
        """
        logger.info(f"Cleaning up STTAudioSink for session {self.session_id}")

        # Stop accepting new audio
        self._processing = False

        # Create snapshot of user IDs to avoid dictionary iteration issues during modification
        user_ids = list(self._user_buffers.keys())
        logger.debug(f"Cleaning up {len(user_ids)} user buffers")

        # Wait for all buffers to be processed (thread-safe iteration)
        for user_id in user_ids:
            if user_id not in self._user_buffers:
                continue

            audio_buffer = self._user_buffers[user_id]
            logger.debug(
                f"Waiting for user {user_id} buffer to empty "
                f"({audio_buffer.qsize()} packets remaining)"
            )

            # Give some time for processing to complete
            timeout = 10.0  # Increased from 5.0 to account for Whisper model loading
            start_time = time.time()
            while not audio_buffer.empty() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not audio_buffer.empty():
                logger.warning(
                    f"User {user_id} buffer still has {audio_buffer.qsize()} "
                    f"packets after {timeout}s timeout"
                )

        # Wait for ALL processing threads to complete before clearing dictionaries
        logger.info("Waiting for all processing threads to complete...")
        threads_snapshot = list(self._processing_threads.items())
        for user_id, thread in threads_snapshot:
            if thread and thread.is_alive():
                logger.debug(f"Joining thread for user {user_id}")
                thread.join(timeout=10.0)  # Wait up to 10 seconds per thread
                if thread.is_alive():
                    logger.warning(f"Thread for user {user_id} did not terminate in time")
                else:
                    logger.debug(f"Thread for user {user_id} completed")

        # Now it's safe to clear all buffers and state
        self._user_buffers.clear()
        self._user_locks.clear()
        self._user_vad_state.clear()
        self._vad_buffers.clear()
        self._chunk_counters.clear()
        self._processing_threads.clear()
        self._first_packet_received.clear()

        # Unload VAD model to free memory
        if self._vad_model is not None:
            del self._vad_model
            self._vad_model = None
            self._vad_utils = None

            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        logger.info(f"STTAudioSink cleanup complete for session {self.session_id}")


def create_audio_sink(
    session_id: int,
    channel_id: int,
    db_instance: Optional[Any] = None,
    whisper_manager: Optional[Any] = None
) -> STTAudioSink:
    """Factory function to create STTAudioSink instance.

    Args:
        session_id: Database session ID for tracking voice session
        channel_id: Discord voice channel ID
        db_instance: ConversationDatabase instance (optional)
        whisper_manager: WhisperModelManager instance (optional)

    Returns:
        Configured STTAudioSink instance
    """
    return STTAudioSink(
        session_id=session_id,
        channel_id=channel_id,
        db_instance=db_instance,
        whisper_manager=whisper_manager
    )
