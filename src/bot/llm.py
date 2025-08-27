import ollama  # type: ignore[import-not-found]
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import os


@dataclass
class MessageContext:
    """Represents a Discord message retrieved from ChromaDB"""

    content: str
    author: str
    channel: str
    timestamp: datetime
    message_id: str
    similarity_score: float = 0.0


@dataclass
class LLMResponse:
    """Response from the LLM with metadata"""

    content: str
    tokens_used: int
    response_time: float
    model_used: str
    success: bool
    error: Optional[str] = None


class DiscordLLMHandler:
    """
    Modular LLM handler for Discord bot using Ollama with Llama 3.2 3B
    Handles context formatting, response generation, and Discord-specific formatting
    """

    def __init__(
        self,
        model_name: str = None,
        max_context_length: Optional[int] = None,
        temperature: Optional[float] = None,
        max_response_length: Optional[int] = None,
    ):  # Discord limit is 2000 chars
        """
        Initialize the LLM handler

        Args:
            model_name: Ollama model name
            max_context_length: Maximum context length for retrieved messages
            temperature: Generation temperature (0.0-1.0)
            max_response_length: Maximum response length for Discord
        """
        # Allow environment configuration with sensible defaults
        self.model_name = model_name or os.getenv(
            "LLM_MODEL_NAME", "llama3.2:3b-instruct"
        )
        self.max_context_length = (
            max_context_length
            if max_context_length is not None
            else int(os.getenv("LLM_MAX_CONTEXT", "4000"))
        )
        self.temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("LLM_TEMPERATURE", "0.7"))
        )
        self.max_response_length = (
            max_response_length
            if max_response_length is not None
            else int(os.getenv("LLM_MAX_RESPONSE", "1800"))
        )
        self.logger = logging.getLogger(__name__)

        # Initialize Ollama client (support custom host via env)
        ollama_host = os.getenv("OLLAMA_HOST")
        if ollama_host:
            self.client = ollama.Client(host=ollama_host)
        else:
            self.client = ollama.Client()
        self._ensure_model_available()

    def _ensure_model_available(self) -> None:
        """Ensure the model is downloaded and available"""
        try:
            # Check if model exists
            models = self.client.list()
            model_names = [model["name"] for model in models["models"]]

            if self.model_name not in model_names:
                self.logger.info(f"Downloading model {self.model_name}...")
                self.client.pull(self.model_name)
                self.logger.info(f"Model {self.model_name} downloaded successfully")
            else:
                self.logger.info(f"Model {self.model_name} is available")

        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
            self.logger.error(f"Error ensuring model availability: {e}")
            raise

    def format_context_messages(self, messages: List[MessageContext]) -> str:
        """
        Format retrieved Discord messages into context for the LLM

        Args:
            messages: List of MessageContext objects from ChromaDB

        Returns:
            Formatted context string
        """
        if not messages:
            return "No relevant messages found in the server history."

        context_parts = []
        current_length = 0

        for msg in messages:
            # Format timestamp
            timestamp_str = msg.timestamp.strftime("%Y-%m-%d %H:%M")

            # Format individual message
            formatted_msg = (
                f"[{timestamp_str}] {msg.author} in #{msg.channel}:\n{msg.content}\n"
            )

            # Check if adding this message exceeds context length
            if current_length + len(formatted_msg) > self.max_context_length:
                break

            context_parts.append(formatted_msg)
            current_length += len(formatted_msg)

        return "\n---\n".join(context_parts)

    def create_system_prompt(self) -> str:
        """Create system prompt for Discord bot context"""
        return """You are a helpful Discord bot assistant that answers questions based on Discord server message history. 

Your role:
- Answer questions using the provided Discord message context
- Be conversational and friendly, matching Discord's casual tone
- If information isn't in the context, say so clearly
- Keep responses under 1800 characters for Discord compatibility
- When referencing specific messages, mention the author and approximate time
- Don't make up information not present in the context

Format your responses to be Discord-friendly:
- Use **bold** for emphasis when needed
- Keep line breaks readable
- Be concise but helpful"""

    def create_user_prompt(self, query: str, context: str) -> str:
        """Create user prompt with query and context"""
        return f"""Based on the Discord message history below, please answer this question: "{query}"

Discord Message History:
{context}

Please provide a helpful answer based on this context."""

    async def generate_response_async(
        self, query: str, retrieved_messages: List[MessageContext]
    ) -> LLMResponse:
        """
        Generate async response using Ollama (runs in thread to avoid blocking)

        Args:
            query: User's question
            retrieved_messages: Messages from ChromaDB semantic search

        Returns:
            LLMResponse object with generated content and metadata
        """
        start_time = datetime.now()

        try:
            # Format context
            context = self.format_context_messages(retrieved_messages)

            # Create prompts
            system_prompt = self.create_system_prompt()
            user_prompt = self.create_user_prompt(query, context)

            # Run generation in thread to avoid blocking
            loop = asyncio.get_running_loop()
            _response = await loop.run_in_executor(
                None, self._generate_sync_response, system_prompt, user_prompt
            )

            response_time = (datetime.now() - start_time).total_seconds()

            # Truncate if too long for Discord
            content = _response["message"]["content"]
            if len(content) > self.max_response_length:
                content = (
                    content[: self.max_response_length - 50]
                    + "\n\n*[Response truncated]*"
                )

            return LLMResponse(
                content=content,
                tokens_used=_response.get("prompt_eval_count", 0)
                + _response.get("eval_count", 0),
                response_time=response_time,
                model_used=self.model_name,
                success=True,
            )

        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
            self.logger.error(f"Error generating response: {e}")
            response_time = (datetime.now() - start_time).total_seconds()

            return LLMResponse(
                content="Sorry, I encountered an error while processing your request.",
                tokens_used=0,
                response_time=response_time,
                model_used=self.model_name,
                success=False,
                error=str(e),
            )

    def _generate_sync_response(
        self, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        """Synchronous generation method for use with run_in_executor"""
        return self.client.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={
                "temperature": self.temperature,
                "num_predict": 500,  # Limit tokens for Discord
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        )

    def generate_response_sync(
        self, query: str, retrieved_messages: List[MessageContext]
    ) -> LLMResponse:
        """
        Synchronous version of response generation

        Args:
            query: User's question
            retrieved_messages: Messages from ChromaDB semantic search

        Returns:
            LLMResponse object with generated content and metadata
        """
        start_time = datetime.now()

        try:
            context = self.format_context_messages(retrieved_messages)
            system_prompt = self.create_system_prompt()
            user_prompt = self.create_user_prompt(query, context)

            response = self._generate_sync_response(system_prompt, user_prompt)
            response_time = (datetime.now() - start_time).total_seconds()

            content = response["message"]["content"]
            if len(content) > self.max_response_length:
                content = (
                    content[: self.max_response_length - 50]
                    + "\n\n*[Response truncated]*"
                )

            return LLMResponse(
                content=content,
                tokens_used=response.get("prompt_eval_count", 0)
                + response.get("eval_count", 0),
                response_time=response_time,
                model_used=self.model_name,
                success=True,
            )

        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
            self.logger.error(f"Error generating response: {e}")
            response_time = (datetime.now() - start_time).total_seconds()

            return LLMResponse(
                content="Sorry, I encountered an error while processing your request.",
                tokens_used=0,
                response_time=response_time,
                model_used=self.model_name,
                success=False,
                error=str(e),
            )

    def health_check(self) -> bool:
        """Check if the model is responsive"""
        try:
            self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hello"}],
                options={"num_predict": 10},
            )
            return True
        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        try:
            models = self.client.list()
            for model in models["models"]:
                if model["name"] == self.model_name:
                    return model
            return {}
        except (ConnectionError, TimeoutError, OSError, ValueError, KeyError, RuntimeError) as e:
            self.logger.error(f"Error getting model info: {e}")
            return {}
