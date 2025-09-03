import logging
import os
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .utils import get_ollama_client, get_model_max_context

try:
    from ..config.settings import settings
except ImportError:
    # Fallback for direct script execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.config.settings import settings


@dataclass
class LLMResponse:
    """Response from the LLM with metadata"""
    
    content: str
    tokens_used: int
    response_time: float
    model_used: str
    success: bool
    error: str = None


def generate_completion_sync(
    prompt: str,
    model_name: str = None,
    temperature: float = None,
    max_tokens: int = None
) -> LLMResponse:
    """
    Generate synchronous chat completion from prompt string
    
    Args:
        prompt: Full conversation prompt (system + user messages formatted as string)
        model_name: Ollama model name (defaults to env LLM_MODEL_NAME or llama3.2:3b-instruct)
        temperature: Generation temperature (defaults to env LLM_TEMPERATURE or 0.7)
        max_tokens: Maximum tokens to generate (defaults to 500)
        
    Returns:
        LLMResponse with generated content and metadata
    """
    logger = logging.getLogger(__name__)
    start_time = datetime.now()
    
    # Set defaults from environment
    model_name = settings.LLM_MODEL_NAME
    temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens = max_tokens or 500
    
    try:
        client = get_ollama_client()
        
        # Get the model's maximum context window
        num_ctx = get_model_max_context(model_name)
        
        # Parse prompt into messages (simple implementation - assumes single user message)
        messages = [{"role": "user", "content": prompt}]
        
        response = client.chat(
            model=model_name,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": num_ctx,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        )
        
        response_time = (datetime.now() - start_time).total_seconds()
        
        return LLMResponse(
            content=response["message"]["content"],
            tokens_used=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
            response_time=response_time,
            model_used=model_name,
            success=True,
        )
        
    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Error generating completion: {e}")
        response_time = (datetime.now() - start_time).total_seconds()
        
        return LLMResponse(
            content="",
            tokens_used=0,
            response_time=response_time,
            model_used=model_name,
            success=False,
            error=str(e),
        )


def generate_completion_with_messages_sync(
    messages: List[Dict[str, str]],
    model_name: str = None,
    temperature: float = None,
    max_tokens: int = None
) -> LLMResponse:
    """
    Generate synchronous chat completion from structured messages
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model_name: Ollama model name
        temperature: Generation temperature
        max_tokens: Maximum tokens to generate
        
    Returns:
        LLMResponse with generated content and metadata
    """
    logger = logging.getLogger(__name__)
    start_time = datetime.now()
    
    # Set defaults from environment
    model_name = model_name or os.getenv("LLM_MODEL_NAME", "llama3.1:8b")
    temperature = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens = max_tokens or 500
    
    try:
        client = get_ollama_client()
        
        # Get the model's maximum context window
        num_ctx = get_model_max_context(model_name)
        
        response = client.chat(
            model=model_name,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": num_ctx,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        )
        
        response_time = (datetime.now() - start_time).total_seconds()
        
        return LLMResponse(
            content=response["message"]["content"],
            tokens_used=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
            response_time=response_time,
            model_used=model_name,
            success=True,
        )
        
    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Error generating completion: {e}")
        response_time = (datetime.now() - start_time).total_seconds()
        
        return LLMResponse(
            content="",
            tokens_used=0,
            response_time=response_time,
            model_used=model_name,
            success=False,
            error=str(e),
        )


async def generate_completion_async(
    prompt: str,
    model_name: str = None,
    temperature: float = None,
    max_tokens: int = None
) -> LLMResponse:
    """
    Generate asynchronous chat completion from prompt string
    
    Args:
        prompt: Full conversation prompt
        model_name: Ollama model name
        temperature: Generation temperature  
        max_tokens: Maximum tokens to generate
        
    Returns:
        LLMResponse with generated content and metadata
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, generate_completion_sync, prompt, model_name, temperature, max_tokens
    )


async def generate_completion_with_messages_async(
    messages: List[Dict[str, str]],
    model_name: str = None,
    temperature: float = None,
    max_tokens: int = None
) -> LLMResponse:
    """
    Generate asynchronous chat completion from structured messages
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model_name: Ollama model name
        temperature: Generation temperature
        max_tokens: Maximum tokens to generate
        
    Returns:
        LLMResponse with generated content and metadata
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, generate_completion_with_messages_sync, messages, model_name, temperature, max_tokens
    )
