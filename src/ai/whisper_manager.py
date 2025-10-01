"""Whisper speech-to-text model manager for Discord-Indexer.

Provides faster-whisper model functionality with Silero VAD integration
for efficient audio transcription with GPU optimization.
"""

import asyncio
import logging
import threading
import torch
import numpy as np
from typing import Optional, Dict, List, Tuple, Union, BinaryIO
from pathlib import Path
from faster_whisper import WhisperModel
from src.exceptions.message_processing import LLMProcessingError
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Global singleton instances for Whisper models
_whisper_instances: Dict[str, 'WhisperModelManager'] = {}
_whisper_lock = threading.Lock()


class WhisperModelManager:
    """Faster-Whisper model manager with Silero VAD integration.

    Implements a singleton pattern to ensure the large Whisper model
    is loaded only once and reused across all instances.

    Supports transcription from both file paths and audio buffers with
    optional voice activity detection for improved accuracy.
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "int8"
    ):
        """Initialize Whisper model manager.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to run model on (cuda/cpu)
            compute_type: Compute precision (int8, int8_float16, float16, float32)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        self._model: Optional[WhisperModel] = None
        self._vad_model: Optional[torch.nn.Module] = None
        self._model_loaded = False
        self._vad_loaded = False
        self._load_lock = threading.Lock()
        self._vad_lock = threading.Lock()

        logger.debug(
            f"Initialized WhisperModelManager with model={model_size}, "
            f"device={device}, compute_type={compute_type}"
        )

    def _load_model(self) -> WhisperModel:
        """Thread-safe lazy loading of the Whisper model.

        Returns:
            Loaded WhisperModel instance

        Raises:
            LLMProcessingError: If model loading fails
        """
        if self._model is None:
            with self._load_lock:
                # Double-check locking pattern
                if self._model is None:
                    try:
                        logger.info(
                            f"Loading Whisper model {self.model_size} on {self.device} "
                            f"with compute_type={self.compute_type} (singleton instance)"
                        )

                        self._model = WhisperModel(
                            self.model_size,
                            device=self.device,
                            compute_type=self.compute_type
                        )

                        self._model_loaded = True
                        logger.info(
                            f"Successfully loaded Whisper model {self.model_size} (singleton instance)"
                        )

                    except Exception as e:
                        logger.error(f"Failed to load Whisper model {self.model_size}: {e}")
                        raise LLMProcessingError(f"Could not load Whisper model: {e}")

        return self._model

    def _load_vad(self) -> torch.nn.Module:
        """Thread-safe lazy loading of the Silero VAD model.

        Returns:
            Loaded Silero VAD model

        Raises:
            LLMProcessingError: If VAD loading fails
        """
        if self._vad_model is None:
            with self._vad_lock:
                # Double-check locking pattern
                if self._vad_model is None:
                    try:
                        logger.info("Loading Silero VAD model (singleton instance)")

                        # Load Silero VAD from torch hub
                        self._vad_model, vad_utils = torch.hub.load(
                            repo_or_dir='snakers4/silero-vad',
                            model='silero_vad',
                            force_reload=False,
                            onnx=False
                        )

                        # Extract utility functions
                        self._get_speech_timestamps = vad_utils[0]
                        self._save_audio = vad_utils[1]
                        self._read_audio = vad_utils[2]
                        self._collect_chunks = vad_utils[4]

                        self._vad_loaded = True
                        logger.info("Successfully loaded Silero VAD model (singleton instance)")

                    except Exception as e:
                        logger.error(f"Failed to load Silero VAD model: {e}")
                        raise LLMProcessingError(f"Could not load Silero VAD model: {e}")

        return self._vad_model

    async def _load_model_async(self) -> None:
        """Load Whisper model asynchronously to prevent event loop blocking.

        Uses thread-safe loading with double-check locking pattern.

        Raises:
            LLMProcessingError: If model loading fails
        """
        if self._model is None:
            await asyncio.to_thread(self._load_model)

    async def _load_vad_async(self) -> None:
        """Load Silero VAD model asynchronously to prevent event loop blocking.

        Uses thread-safe loading with double-check locking pattern.

        Raises:
            LLMProcessingError: If VAD loading fails
        """
        if self._vad_model is None:
            await asyncio.to_thread(self._load_vad)

    def _apply_vad_filter(self, audio_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Apply Silero VAD to extract speech segments from audio.

        Args:
            audio_path: Path to audio file

        Returns:
            Filtered audio as numpy array, or None if no speech detected

        Raises:
            LLMProcessingError: If VAD processing fails
        """
        try:
            # Ensure VAD is loaded
            if self._vad_model is None:
                self._load_vad()

            # Read audio file
            wav = self._read_audio(str(audio_path), sampling_rate=16000)

            # Get speech timestamps
            speech_timestamps = self._get_speech_timestamps(
                wav,
                self._vad_model,
                sampling_rate=16000,
                threshold=0.5,
                min_speech_duration_ms=250,
                min_silence_duration_ms=settings.STT_SILENCE_DURATION_MS
            )

            if not speech_timestamps:
                logger.warning(f"No speech detected in audio: {audio_path}")
                return None

            # Collect speech chunks
            filtered_audio = self._collect_chunks(speech_timestamps, wav)

            return filtered_audio

        except Exception as e:
            logger.error(f"VAD filtering failed for {audio_path}: {e}")
            raise LLMProcessingError(f"VAD filtering failed: {e}")

    def transcribe(
        self,
        audio_path: Union[str, Path],
        vad_filter: bool = True,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict[str, Union[str, List[Dict]]]:
        """Transcribe audio file with optional VAD filtering.

        Args:
            audio_path: Path to audio file
            vad_filter: Whether to apply VAD filtering before transcription
            language: Source language code (None for auto-detection)
            task: Task type ("transcribe" or "translate")

        Returns:
            Dictionary containing:
                - text: Full transcription text
                - segments: List of segment dictionaries with timestamps
                - language: Detected/specified language

        Raises:
            LLMProcessingError: If transcription fails
        """
        try:
            # Ensure model is loaded
            if self._model is None:
                self._load_model()

            audio_path = Path(audio_path)

            if not audio_path.exists():
                raise LLMProcessingError(f"Audio file not found: {audio_path}")

            # Apply VAD filtering if requested
            if vad_filter:
                logger.debug(f"Applying VAD filter to {audio_path}")
                filtered_audio = self._apply_vad_filter(audio_path)

                if filtered_audio is None:
                    return {
                        "text": "",
                        "segments": [],
                        "language": language or "unknown"
                    }

            # Transcribe audio
            logger.debug(f"Transcribing audio: {audio_path}")
            segments, info = self._model.transcribe(
                str(audio_path),
                language=language,
                task=task,
                vad_filter=vad_filter,
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=settings.STT_SILENCE_DURATION_MS
                ) if vad_filter else None
            )

            # Convert segments to list and extract text
            segment_list = []
            full_text = []

            for segment in segments:
                segment_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "avg_logprob": segment.avg_logprob,
                    "no_speech_prob": segment.no_speech_prob
                }
                segment_list.append(segment_dict)
                full_text.append(segment.text.strip())

            result = {
                "text": " ".join(full_text),
                "segments": segment_list,
                "language": info.language
            }

            logger.debug(
                f"Transcription completed: {len(segment_list)} segments, "
                f"language={info.language}"
            )

            return result

        except LLMProcessingError:
            raise
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path}: {e}")
            raise LLMProcessingError(f"Transcription failed: {e}")

    async def transcribe_async(
        self,
        audio_path: Union[str, Path],
        vad_filter: bool = True,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict[str, Union[str, List[Dict]]]:
        """Transcribe audio file asynchronously.

        Args:
            audio_path: Path to audio file
            vad_filter: Whether to apply VAD filtering before transcription
            language: Source language code (None for auto-detection)
            task: Task type ("transcribe" or "translate")

        Returns:
            Dictionary containing transcription results

        Raises:
            LLMProcessingError: If transcription fails
        """
        # Ensure model is loaded asynchronously
        if self._model is None:
            await self._load_model_async()

        # Run transcription in thread pool
        return await asyncio.to_thread(
            self.transcribe,
            audio_path,
            vad_filter,
            language,
            task
        )

    def transcribe_buffer(
        self,
        audio_data: Union[np.ndarray, bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict[str, Union[str, List[Dict]]]:
        """Transcribe audio from in-memory buffer.

        Args:
            audio_data: Audio data as numpy array or bytes
            sample_rate: Audio sample rate in Hz
            language: Source language code (None for auto-detection)
            task: Task type ("transcribe" or "translate")

        Returns:
            Dictionary containing transcription results

        Raises:
            LLMProcessingError: If transcription fails
        """
        try:
            # Ensure model is loaded
            if self._model is None:
                self._load_model()

            # Convert bytes to numpy array if needed
            if isinstance(audio_data, bytes):
                audio_data = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # Transcribe audio buffer
            logger.debug(f"Transcribing audio buffer (sample_rate={sample_rate})")
            segments, info = self._model.transcribe(
                audio_data,
                language=language,
                task=task
            )

            # Convert segments to list and extract text
            segment_list = []
            full_text = []

            for segment in segments:
                segment_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "avg_logprob": segment.avg_logprob,
                    "no_speech_prob": segment.no_speech_prob
                }
                segment_list.append(segment_dict)
                full_text.append(segment.text.strip())

            result = {
                "text": " ".join(full_text),
                "segments": segment_list,
                "language": info.language
            }

            logger.debug(
                f"Buffer transcription completed: {len(segment_list)} segments, "
                f"language={info.language}"
            )

            return result

        except Exception as e:
            logger.error(f"Buffer transcription failed: {e}")
            raise LLMProcessingError(f"Buffer transcription failed: {e}")

    async def transcribe_buffer_async(
        self,
        audio_data: Union[np.ndarray, bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict[str, Union[str, List[Dict]]]:
        """Transcribe audio buffer asynchronously.

        Args:
            audio_data: Audio data as numpy array or bytes
            sample_rate: Audio sample rate in Hz
            language: Source language code (None for auto-detection)
            task: Task type ("transcribe" or "translate")

        Returns:
            Dictionary containing transcription results

        Raises:
            LLMProcessingError: If transcription fails
        """
        # Ensure model is loaded asynchronously
        if self._model is None:
            await self._load_model_async()

        # Run transcription in thread pool
        return await asyncio.to_thread(
            self.transcribe_buffer,
            audio_data,
            sample_rate,
            language,
            task
        )

    def unload_model(self) -> None:
        """Unload Whisper model from memory to free VRAM.

        This method releases the model and allows CUDA to reclaim memory.
        The model will be automatically reloaded on next use.
        """
        with self._load_lock:
            if self._model is not None:
                logger.info(f"Unloading Whisper model {self.model_size}")
                del self._model
                self._model = None
                self._model_loaded = False

                # Force CUDA memory cleanup if using GPU
                if self.device == "cuda" and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.debug("Cleared CUDA cache after model unload")

    def unload_vad(self) -> None:
        """Unload Silero VAD model from memory.

        The VAD model will be automatically reloaded on next use.
        """
        with self._vad_lock:
            if self._vad_model is not None:
                logger.info("Unloading Silero VAD model")
                del self._vad_model
                self._vad_model = None
                self._vad_loaded = False

                # Clear utility functions
                self._get_speech_timestamps = None
                self._save_audio = None
                self._read_audio = None
                self._collect_chunks = None

    def unload_all(self) -> None:
        """Unload both Whisper and VAD models from memory."""
        self.unload_model()
        self.unload_vad()

    def is_loaded(self) -> bool:
        """Check if Whisper model is currently loaded.

        Returns:
            True if model is loaded in memory, False otherwise
        """
        return self._model_loaded and self._model is not None

    def is_vad_loaded(self) -> bool:
        """Check if Silero VAD model is currently loaded.

        Returns:
            True if VAD is loaded in memory, False otherwise
        """
        return self._vad_loaded and self._vad_model is not None


def get_whisper_manager(
    model_size: Optional[str] = None,
    device: Optional[str] = None,
    compute_type: Optional[str] = None
) -> WhisperModelManager:
    """Get a singleton Whisper model manager instance.

    This function implements the singleton pattern to ensure that only one
    instance of each Whisper model configuration is created and reused.
    This prevents the expensive model loading process from happening multiple times.

    Args:
        model_size: Whisper model size (defaults to settings.WHISPER_MODEL)
        device: Device to run on (defaults to settings.WHISPER_DEVICE)
        compute_type: Compute precision (defaults to settings.WHISPER_COMPUTE_TYPE)

    Returns:
        WhisperModelManager singleton instance

    Raises:
        LLMProcessingError: If manager creation fails
    """
    global _whisper_instances, _whisper_lock

    # Use settings defaults if not specified
    model_size = model_size or settings.WHISPER_MODEL
    device = device or settings.WHISPER_DEVICE
    compute_type = compute_type or settings.WHISPER_COMPUTE_TYPE

    # Create unique key for this configuration
    instance_key = f"{model_size}_{device}_{compute_type}"

    # Thread-safe singleton access
    with _whisper_lock:
        if instance_key not in _whisper_instances:
            try:
                logger.info(
                    f"Creating singleton WhisperModelManager instance: {instance_key}"
                )
                _whisper_instances[instance_key] = WhisperModelManager(
                    model_size=model_size,
                    device=device,
                    compute_type=compute_type
                )
            except Exception as e:
                logger.error(f"Failed to create WhisperModelManager: {e}")
                raise LLMProcessingError(f"Could not create Whisper manager: {e}")
        else:
            logger.debug(
                f"Reusing existing singleton WhisperModelManager instance: {instance_key}"
            )

        return _whisper_instances[instance_key]


async def preload_whisper_manager(
    model_size: Optional[str] = None,
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    load_vad: bool = True
) -> WhisperModelManager:
    """Preload Whisper model manager asynchronously during startup.

    This function should be called during application startup to load the
    Whisper model asynchronously, preventing blocking during runtime.

    Args:
        model_size: Whisper model size (defaults to settings.WHISPER_MODEL)
        device: Device to run on (defaults to settings.WHISPER_DEVICE)
        compute_type: Compute precision (defaults to settings.WHISPER_COMPUTE_TYPE)
        load_vad: Whether to also preload the Silero VAD model

    Returns:
        Preloaded WhisperModelManager instance

    Raises:
        LLMProcessingError: If preloading fails
    """
    try:
        logger.info("Preloading Whisper model manager")
        manager = get_whisper_manager(model_size, device, compute_type)

        # Load model asynchronously
        await manager._load_model_async()

        # Load VAD if requested
        if load_vad:
            await manager._load_vad_async()

        logger.info("Successfully preloaded Whisper model manager")
        return manager

    except Exception as e:
        logger.error(f"Failed to preload Whisper model manager: {e}")
        raise LLMProcessingError(f"Could not preload Whisper manager: {e}")


def clear_whisper_manager() -> None:
    """Clear all cached Whisper manager instances.

    This function unloads all models and clears the instance cache.
    Use with caution in production as it will cause models to be reloaded.
    """
    global _whisper_instances
    with _whisper_lock:
        logger.info("Clearing Whisper manager cache")

        # Unload all models before clearing
        for manager in _whisper_instances.values():
            manager.unload_all()

        _whisper_instances.clear()

        # Force CUDA cleanup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("Cleared CUDA cache")


def get_loaded_managers() -> List[str]:
    """Get list of currently loaded Whisper manager configurations.

    Returns:
        List of configuration keys that have loaded models
    """
    global _whisper_instances
    with _whisper_lock:
        return [
            key for key, manager in _whisper_instances.items()
            if manager.is_loaded()
        ]


def get_supported_models() -> List[str]:
    """Get list of supported Whisper model sizes.

    Returns:
        List of supported model size names
    """
    return [
        "tiny",
        "tiny.en",
        "base",
        "base.en",
        "small",
        "small.en",
        "medium",
        "medium.en",
        "large-v2",
        "large-v3"
    ]


def get_supported_compute_types() -> List[str]:
    """Get list of supported compute types for faster-whisper.

    Returns:
        List of supported compute type names
    """
    return [
        "int8",
        "int8_float16",
        "float16",
        "float32"
    ]
