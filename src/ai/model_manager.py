import logging
import time
from typing import Dict, Any, Tuple

from src.config.settings import settings
from src.ai.utils import get_ollama_client, ensure_model_available, health_check


logger = logging.getLogger(__name__)


class ModelManager:
    """
    Manages simultaneous lifecycle of text and vision models for local LLM operations.
    
    Handles loading both models into Ollama memory with proper keep_alive settings,
    provides model name access, and health checking for both models. Designed to
    support Discord bot pattern of simultaneous loading with sequential usage.
    
    Fails hard if models cannot be loaded simultaneously - no fallback logic.
    """
    
    def __init__(self) -> None:
        """
        Initialize ModelManager and load both models into memory.
        
        Raises:
            ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError:
                If models cannot be loaded simultaneously
        """
        self._text_model_name = settings.TEXT_MODEL_NAME
        self._vision_model_name = settings.VISION_MODEL_NAME
        self._models_loaded = False
        
        logger.info(f"Initializing ModelManager with text={self._text_model_name}, vision={self._vision_model_name}")
        
        # Load both models during initialization
        self.ensure_models_loaded()
    
    def ensure_models_loaded(self) -> None:
        """
        Ensure both text and vision models are loaded into Ollama memory simultaneously.
        
        Uses '30m' keep_alive setting to prevent unloading. Loads vision model first,
        then text model, both with keep_alive to maintain in memory.
        
        Raises:
            ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError:
                If either model cannot be loaded or kept in memory
        """
        try:
            logger.info("Starting simultaneous model loading...")
            start_time = time.time()
            
            # Ensure models are available first
            logger.info(f"Ensuring vision model {self._vision_model_name} is available...")
            ensure_model_available(self._vision_model_name)
            
            logger.info(f"Ensuring text model {self._text_model_name} is available...")
            ensure_model_available(self._text_model_name)
            
            # Load vision model into memory first
            logger.info(f"Loading vision model {self._vision_model_name} into memory...")
            vision_start = time.time()
            
            client = get_ollama_client()
            client.chat(
                model=self._vision_model_name,
                messages=[{"role": "user", "content": "Hello"}],
                options={"num_predict": 10},
                keep_alive="30m"
            )
            
            vision_load_time = time.time() - vision_start
            logger.info(f"Vision model loaded in {vision_load_time:.2f} seconds")
            
            # Load text model into memory second
            logger.info(f"Loading text model {self._text_model_name} into memory...")
            text_start = time.time()
            
            client.chat(
                model=self._text_model_name,
                messages=[{"role": "user", "content": "Hello"}],
                options={"num_predict": 10},
                keep_alive="30m"
            )
            
            text_load_time = time.time() - text_start
            logger.info(f"Text model loaded in {text_load_time:.2f} seconds")
            
            total_load_time = time.time() - start_time
            logger.info(f"Both models loaded successfully in {total_load_time:.2f} seconds total")
            
            self._models_loaded = True
            
        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Failed to load models simultaneously: {e}")
            self._models_loaded = False
            raise RuntimeError(f"Failed to ensure models loaded: {e}") from e
    
    def get_text_model(self) -> str:
        """
        Get the text model name for use by other components.
        
        Returns:
            The text model name from settings
            
        Raises:
            RuntimeError: If models have not been loaded successfully
        """
        if not self._models_loaded:
            raise RuntimeError("Models not loaded - call ensure_models_loaded() first")
        
        return self._text_model_name
    
    def get_vision_model(self) -> str:
        """
        Get the vision model name for use by other components.
        
        Returns:
            The vision model name from settings
            
        Raises:
            RuntimeError: If models have not been loaded successfully
        """
        if not self._models_loaded:
            raise RuntimeError("Models not loaded - call ensure_models_loaded() first")
        
        return self._vision_model_name
    
    def health_check_both_models(self) -> Dict[str, Any]:
        """
        Perform health check on both text and vision models to ensure responsiveness.
        
        Returns:
            Dictionary containing health status for both models with timing information
            Format: {
                'text_model': {'healthy': bool, 'response_time': float, 'error': str|None},
                'vision_model': {'healthy': bool, 'response_time': float, 'error': str|None},
                'both_healthy': bool,
                'total_check_time': float
            }
            
        Raises:
            RuntimeError: If models have not been loaded successfully
        """
        if not self._models_loaded:
            raise RuntimeError("Models not loaded - call ensure_models_loaded() first")
        
        logger.info("Starting health check for both models...")
        start_time = time.time()
        
        # Health check text model
        text_start = time.time()
        text_healthy = health_check(self._text_model_name)
        text_time = time.time() - text_start
        
        # Health check vision model
        vision_start = time.time()
        vision_healthy = health_check(self._vision_model_name)
        vision_time = time.time() - vision_start
        
        total_time = time.time() - start_time
        both_healthy = text_healthy and vision_healthy
        
        result = {
            'text_model': {
                'healthy': text_healthy,
                'response_time': text_time,
                'error': None if text_healthy else f"Text model {self._text_model_name} health check failed"
            },
            'vision_model': {
                'healthy': vision_healthy,
                'response_time': vision_time,
                'error': None if vision_healthy else f"Vision model {self._vision_model_name} health check failed"
            },
            'both_healthy': both_healthy,
            'total_check_time': total_time
        }
        
        if both_healthy:
            logger.info(f"Health check passed for both models in {total_time:.2f} seconds")
        else:
            logger.warning(f"Health check failed - text:{text_healthy}, vision:{vision_healthy}")
        
        return result