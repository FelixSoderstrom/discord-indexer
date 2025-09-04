import ollama  # type: ignore[import-not-found]
import logging
import os
import subprocess
import re
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


def get_ollama_client() -> ollama.Client:
    """
    Get configured Ollama client
    
    Returns:
        Configured Ollama client instance
    """
    ollama_host = os.getenv("OLLAMA_HOST")
    if ollama_host:
        return ollama.Client(host=ollama_host)
    else:
        return ollama.Client()


def ensure_model_available(model_name: str = "llama3.1:8b") -> None:
    """
    Ensure the specified model is downloaded and available
    
    Args:
        model_name: Name of the model to check/download
        
    Raises:
        ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError: 
            If model cannot be ensured available
    """
    try:
        client = get_ollama_client()
        
        # Check if model exists
        models = client.list()
        model_names = [model.get("name", model.get("model", "")) for model in models.get("models", [])]

        if model_name not in model_names:
            logger.info(f"Downloading model {model_name}...")
            client.pull(model_name)
            logger.info(f"Model {model_name} downloaded successfully")
        else:
            logger.info(f"Model {model_name} is available")

    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Error ensuring model availability: {e}")
        raise


def health_check(model_name: str) -> bool:
    """
    Check if the specified model is responsive
    
    Args:
        model_name: Name of the model to health check
        
    Returns:
        True if model is responsive, False otherwise
    """
    try:
        client = get_ollama_client()
        client.chat(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            options={"num_predict": 10},
        )
        return True
    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Health check failed: {e}")
        return False


def get_model_info(model_name: str) -> Dict[str, Any]:
    """
    Get information about the specified model
    
    Args:
        model_name: Name of the model to get info for
        
    Returns:
        Model information dictionary, empty dict if model not found or error
    """
    try:
        client = get_ollama_client()
        models = client.list()
        for model in models.get("models", []):
            if model.get("name", model.get("model", "")) == model_name:
                return model
        return {}
    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Error getting model info: {e}")
        return {}


# Cache for model context windows to avoid repeated subprocess calls
_model_context_cache: Dict[str, int] = {}


def get_model_max_context(model_name: str) -> int:
    """
    Get the maximum context window size for the specified model
    
    Args:
        model_name: Name of the model to get context window for
        
    Returns:
        Maximum context window size in tokens, defaults to 2048 if detection fails
    """
    # Check cache first
    if model_name in _model_context_cache:
        logger.debug(f"Using cached context window for {model_name}: {_model_context_cache[model_name]}")
        return _model_context_cache[model_name]
    
    # Special case for mistral-nemo due to incorrect model metadata
    if "mistral-nemo" in model_name.lower():
        logger.info(f"Using corrected context window for {model_name}: 100000 tokens")
        _model_context_cache[model_name] = 100000
        return 100000
    
    try:
        # Use ollama show command to get detailed model information
        result = subprocess.run(
            ['ollama', 'show', model_name], 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode != 0:
            logger.warning(f"Failed to get model info for {model_name}: {result.stderr}")
            # Cache default and return
            _model_context_cache[model_name] = 2048
            return 2048
        
        # Parse context length from output
        # Looking for patterns like "context length    32768" or "context length: 32768"
        context_match = re.search(r'context\s+length[:\s]+(\d+)', result.stdout, re.IGNORECASE)
        
        if context_match:
            context_window = int(context_match.group(1))
            logger.info(f"Detected context window for {model_name}: {context_window} tokens")
            # Cache the result
            _model_context_cache[model_name] = context_window
            return context_window
        else:
            logger.warning(f"Could not parse context length from model info for {model_name}")
            # Cache default and return
            _model_context_cache[model_name] = 2048
            return 2048
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        logger.error(f"Error getting context window for {model_name}: {e}")
        # Cache default and return
        _model_context_cache[model_name] = 2048
        return 2048


def unload_model_from_memory(model_name: str) -> bool:
    """
    Instantly unload a model from ollama memory
    
    Args:
        model_name: Name of the model to unload from memory
        
    Returns:
        True if unload request was successful, False otherwise
    """
    try:
        client = get_ollama_client()
        
        # Send a minimal request with keep_alive=0 to unload the model
        client.chat(
            model=model_name,
            messages=[{"role": "user", "content": "unload"}],
            options={"num_predict": 1},
            keep_alive=0,
        )
        
        logger.info(f"Successfully unloaded model {model_name} from memory")
        return True
        
    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Error unloading model {model_name}: {e}")
        return False
