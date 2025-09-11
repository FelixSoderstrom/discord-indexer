import logging
import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from src.llm.utils import ensure_model_available, health_check, get_ollama_client
from src.llm.agents.tools.search_tool import create_search_tool

try:
    from src.config.settings import settings
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
    
    async def respond_to_dm(self, message: str, user_id: str, user_name: str = None, server_id: str = None) -> str:
        """
        Generate response to a Discord DM using Ollama native tool calling
        
        Args:
            message: User's message content
            user_id: Discord user ID (for conversation tracking)
            user_name: Optional user name for logging
            server_id: Discord server ID for tool context (REQUIRED)
            
        Returns:
            Generated response text, truncated for Discord if needed
        """
        if not server_id:
            return "❌ **Configuration Error**: No server specified for search. Please end conversation and start again with `!ask`."
        # Build full conversation with context
        full_conversation = self._build_full_conversation(user_id, message)
        
        # Define tool schema for Ollama native tool calling
        tools = [{
            'type': 'function',
            'function': {
                'name': 'search_messages',
                'description': 'Search Discord message history for relevant content. Use this when users ask about past conversations, specific topics, or what someone said about something.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query to find relevant messages (e.g., "Carl XVI Gustaf", "project deadline", "standup meeting")',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return (default: 5)',
                            'default': 5
                        }
                    },
                    'required': ['query'],
                },
            },
        }]
        
        try:
            # Get Ollama client and make tool-aware chat request
            client = get_ollama_client()
            
            response = client.chat(
                model=self.model_name,
                messages=full_conversation,
                tools=tools,
                options={
                    'temperature': self.temperature,
                    'num_predict': 500
                }
            )
            
            # Handle tool calls if present
            if 'tool_calls' in response['message']:
                response_content = await self._handle_native_tool_calls(
                    response['message'], server_id, full_conversation, tools
                )
            else:
                response_content = response['message']['content']
            
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
            self.logger.info(f"DM response generated for {user_display}")
            
            return response_content
            
        except Exception as e:
            self.logger.error(f"Error in DM response generation: {e}")
            return "Sorry, I'm having trouble processing your message right now. Please try again later."
    
    async def _handle_native_tool_calls(self, message_with_tools, server_id: str, conversation: List[Dict], tools: List[Dict]) -> str:
        """Handle native Ollama tool calls.
        
        Args:
            message_with_tools: Message containing tool calls from Ollama
            server_id: Discord server ID for tool context  
            conversation: Full conversation context
            tools: Tool definitions
            
        Returns:
            Final response after tool execution
        """
        try:
            # Add the assistant message with tool calls to conversation
            conversation.append(message_with_tools)
            
            # Execute each tool call
            for tool_call in message_with_tools['tool_calls']:
                function_name = tool_call['function']['name']
                function_args = tool_call['function']['arguments']
                
                if function_name == 'search_messages':
                    # Execute search tool
                    query = function_args['query']
                    limit = function_args.get('limit', 5)
                    
                    self.logger.info(f"Executing search_messages: {query}")
                    
                    # Create search tool and execute
                    search_tool = create_search_tool(server_id)
                    search_results = search_tool.search_messages(query, limit)
                    formatted_results = search_tool.format_search_results(search_results)
                    
                    # Add tool result to conversation
                    conversation.append({
                        'role': 'tool',
                        'content': formatted_results,
                        'tool_call_id': tool_call.get('id', 'search_1')
                    })
            
            # Get final response with tool results
            client = get_ollama_client()
            final_response = client.chat(
                model=self.model_name,
                messages=conversation,
                tools=tools,
                options={
                    'temperature': self.temperature,
                    'num_predict': 500
                }
            )
            
            return final_response['message']['content']
            
        except Exception as e:
            self.logger.error(f"Error handling native tool calls: {e}")
            return "I tried to search the message history but encountered an error. Please try rephrasing your question."
            
    
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
