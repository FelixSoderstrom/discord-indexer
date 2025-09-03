import logging
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from ..chat_completion import generate_completion_with_messages_async, LLMResponse
from ..utils import ensure_model_available, health_check

try:
    from ...config.settings import settings
except ImportError:
    # Fallback for direct script execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from src.config.settings import settings


@dataclass
class MessageContext:
    """Represents a Discord message retrieved from ChromaDB"""
    
    content: str
    author: str
    channel: str
    timestamp: datetime
    message_id: str
    similarity_score: float = 0.0


class DMAssistant:
    """
    Discord DM Assistant with conversation memory and context management
    """
    
    def __init__(
        self,
        model_name: str = None,
        temperature: float = None,
        max_response_length: int = None,
        max_context_messages: int = None
    ):
        """
        Initialize the DM Assistant
        
        Args:
            model_name: Ollama model name
            temperature: Generation temperature
            max_response_length: Maximum response length for Discord
            max_context_messages: Maximum number of conversation messages to keep
        """
        self.model_name = model_name or settings.LLM_MODEL_NAME
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
        self.max_context_messages = (
            max_context_messages 
            if max_context_messages is not None 
            else int(os.getenv("LLM_MAX_CONTEXT_MESSAGES", "20"))
        )
        
        self.logger = logging.getLogger(__name__)
        
        # Conversation storage: user_id -> list of messages
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        # Ensure model is available
        ensure_model_available(self.model_name)
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from text file"""
        try:
            prompt_file = os.path.join(
                os.path.dirname(__file__), 
                "sys_prompts", 
                "dm_assistant.txt"
            )
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError as e:
            self.logger.error(f"Error loading system prompt: {e}")
            # Fallback system prompt
            return "You are a helpful Discord DM assistant. Be conversational and friendly."
    
    def _get_conversation_messages(self, user_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        return self.conversations[user_id]
    
    def _add_message_to_conversation(self, user_id: str, role: str, content: str) -> None:
        """Add message to conversation history"""
        conversation = self._get_conversation_messages(user_id)
        conversation.append({"role": role, "content": content})
        
        # Trim conversation if too long (keep system message + recent messages)
        if len(conversation) > self.max_context_messages:
            # Keep first message (system) and trim from the middle
            conversation[:] = conversation[:1] + conversation[-(self.max_context_messages-1):]
    
    def _build_full_conversation(self, user_id: str, new_message: str) -> List[Dict[str, str]]:
        """Build full conversation including system prompt and history"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add conversation history
        conversation = self._get_conversation_messages(user_id)
        messages.extend(conversation)
        
        # Add new user message
        messages.append({"role": "user", "content": new_message})
        
        return messages
    
    def clear_conversation(self, user_id: str) -> None:
        """Clear conversation history for a user"""
        if user_id in self.conversations:
            del self.conversations[user_id]
            self.logger.info(f"Cleared conversation for user {user_id}")
    
    def get_conversation_length(self, user_id: str) -> int:
        """Get number of messages in conversation"""
        return len(self._get_conversation_messages(user_id))
    
    async def respond_to_dm(self, message: str, user_id: str, user_name: str = None) -> str:
        """
        Generate response to a Discord DM
        
        Args:
            message: User's message content
            user_id: Discord user ID (for conversation tracking)
            user_name: Optional user name for logging
            
        Returns:
            Generated response text, truncated for Discord if needed
        """
        try:
            # Build full conversation with context
            full_conversation = self._build_full_conversation(user_id, message)
            
            # Generate response using chat completion API
            llm_response = await generate_completion_with_messages_async(
                messages=full_conversation,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=500
            )
            
            if not llm_response.success:
                self.logger.error(f"LLM generation failed: {llm_response.error}")
                return "Sorry, I'm having trouble processing your message right now. Please try again later."
            
            response_content = llm_response.content
            
            # Truncate if too long for Discord
            if len(response_content) > self.max_response_length:
                response_content = (
                    response_content[:self.max_response_length - 50] 
                    + "\n\n*[Response truncated]*"
                )
            
            # Add both messages to conversation history
            self._add_message_to_conversation(user_id, "user", message)
            self._add_message_to_conversation(user_id, "assistant", response_content)
            
            # Log the interaction
            user_display = user_name or user_id
            self.logger.info(
                f"DM response generated for {user_display} "
                f"({llm_response.tokens_used} tokens, {llm_response.response_time:.2f}s)"
            )
            
            return response_content
            
        except Exception as e:
            self.logger.error(f"Error generating DM response: {e}")
            return "Sorry, I encountered an error while processing your message."
    
    def health_check(self) -> bool:
        """Check if the assistant is healthy and ready"""
        return health_check(self.model_name)
    
    def get_stats(self) -> Dict:
        """Get assistant statistics"""
        total_conversations = len(self.conversations)
        total_messages = sum(len(conv) for conv in self.conversations.values())
        
        return {
            "model_name": self.model_name,
            "active_conversations": total_conversations,
            "total_messages": total_messages,
            "max_context_messages": self.max_context_messages,
            "max_response_length": self.max_response_length
        }
