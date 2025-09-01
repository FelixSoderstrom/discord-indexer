import ollama  # type: ignore[import-not-found]
import logging
import os
from typing import Dict, Any


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
