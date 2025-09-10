"""LangChain-based Discord DM Assistant.

Replaces the custom DMAssistant with a LangChain agent that provides
reliable tool calling, async execution, and better conversation management.
"""

import logging
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from langchain_ollama import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .tools.langchain_search_tool import create_server_specific_search_tool

try:
    from ...config.settings import settings
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from src.config.settings import settings


logger = logging.getLogger(__name__)


class LangChainDMAssistant:
    """LangChain-powered Discord DM Assistant with tool calling and conversation memory."""
    
    def __init__(
        self,
        model_name: str = None,
        temperature: float = None,
        max_response_length: int = None,
        max_context_messages: int = None
    ):
        """Initialize the LangChain DM Assistant.
        
        Args:
            model_name: Ollama model name
            temperature: Generation temperature
            max_response_length: Maximum response length for Discord
            max_context_messages: Maximum conversation history to maintain
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
        
        # Initialize base LangChain components (agent will be created per-server)
        self._initialize_base_langchain()
        
        # Server-specific agents cache: server_id -> AgentExecutor
        self._server_agents: Dict[str, AgentExecutor] = {}
    
    def _initialize_base_langchain(self):
        """Initialize base LangChain components (LLM and prompt)."""
        try:
            # Create Ollama LLM
            self.llm = ChatOllama(
                model=self.model_name,
                temperature=self.temperature,
                base_url="http://localhost:11434",
                num_predict=500
            )
            
            # Load system prompt
            system_prompt = self._load_system_prompt()
            
            # Create prompt template
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}")
            ])
            
            self.logger.info(f"LangChain DM Assistant base components initialized with model: {self.model_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize base LangChain components: {e}")
            raise
    
    def _get_or_create_server_agent(self, server_id: str) -> AgentExecutor:
        """Get or create an agent executor bound to a specific server.
        
        Args:
            server_id: Discord server ID
            
        Returns:
            AgentExecutor configured for this server
        """
        # Check if we already have an agent for this server
        if server_id in self._server_agents:
            return self._server_agents[server_id]
        
        try:
            # Create server-specific search tool
            server_search_tool = create_server_specific_search_tool(server_id)
            server_tools = [server_search_tool]
            
            # Create agent for this server
            server_agent = create_tool_calling_agent(
                llm=self.llm,
                tools=server_tools,
                prompt=self.prompt
            )
            
            # Create agent executor
            agent_executor = AgentExecutor(
                agent=server_agent,
                tools=server_tools,
                verbose=True,
                max_iterations=3,
                max_execution_time=30,  # 30 second timeout
                handle_parsing_errors=True
            )
            
            # Cache the agent executor
            self._server_agents[server_id] = agent_executor
            
            self.logger.info(f"Created server-specific agent for server {server_id}")
            return agent_executor
            
        except Exception as e:
            self.logger.error(f"Failed to create server agent for {server_id}: {e}")
            raise
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from text file."""
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
            return """You are a helpful Discord DM assistant with access to search Discord message history. 
Be conversational, friendly, and helpful. Keep responses under 1800 characters for Discord compatibility.
Use the search_discord_messages tool when users ask about past conversations or events."""
    
    def _get_conversation_messages(self, user_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a user."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        return self.conversations[user_id]
    
    def _add_message_to_conversation(self, user_id: str, role: str, content: str) -> None:
        """Add message to conversation history."""
        conversation = self._get_conversation_messages(user_id)
        conversation.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
        
        # Trim conversation if too long
        if len(conversation) > self.max_context_messages:
            conversation[:] = conversation[-(self.max_context_messages):]
    
    def _build_chat_history(self, user_id: str) -> List:
        """Build LangChain-compatible chat history."""
        conversation = self._get_conversation_messages(user_id)
        chat_history = []
        
        for msg in conversation:
            if msg["role"] == "user":
                chat_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                chat_history.append(AIMessage(content=msg["content"]))
        
        return chat_history
    
    async def respond_to_dm(
        self, 
        message: str, 
        user_id: str, 
        user_name: str = None, 
        server_id: str = None
    ) -> str:
        """Generate response using LangChain agent.
        
        Args:
            message: User's message content
            user_id: Discord user ID
            user_name: Optional user name for logging
            server_id: Discord server ID for tool context (REQUIRED)
            
        Returns:
            Generated response text
        """
        if not server_id:
            return "❌ **Configuration Error**: No server specified for search. Please end conversation and start again with `!ask`."
        
        try:
            # Get server-specific agent executor
            agent_executor = self._get_or_create_server_agent(server_id)
            
            # Build chat history
            chat_history = self._build_chat_history(user_id)
            
            # Prepare input (no need for server_id since tool is already bound)
            agent_input = {
                "input": message,
                "chat_history": chat_history
            }
            
            # Run server-specific agent asynchronously with timeout
            response = await asyncio.wait_for(
                agent_executor.ainvoke(agent_input),
                timeout=45.0  # 45 second timeout
            )
            
            # Extract response content
            response_content = response.get("output", "I'm sorry, I couldn't generate a response.")
            
            # Truncate if too long for Discord
            if len(response_content) > self.max_response_length:
                response_content = (
                    response_content[:self.max_response_length - 50] 
                    + "\n\n*[Response truncated]*"
                )
            
            # Add messages to conversation history
            self._add_message_to_conversation(user_id, "user", message)
            self._add_message_to_conversation(user_id, "assistant", response_content)
            
            # Log interaction
            user_display = user_name or user_id
            self.logger.info(f"LangChain DM response generated for {user_display}")
            
            return response_content
            
        except asyncio.TimeoutError:
            self.logger.error(f"LangChain agent timeout for user {user_id}")
            return "⏰ **Request Timeout**: Your request took too long to process. Please try a simpler question."
        
        except Exception as e:
            self.logger.error(f"Error in LangChain DM response: {e}")
            return "❌ **Processing Error**: I encountered an issue while processing your message. Please try again."
    
    def clear_conversation(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        if user_id in self.conversations:
            del self.conversations[user_id]
            self.logger.info(f"Cleared conversation for user {user_id}")
    
    def get_conversation_length(self, user_id: str) -> int:
        """Get number of messages in conversation."""
        return len(self._get_conversation_messages(user_id))
    
    def health_check(self) -> bool:
        """Check if the assistant is healthy and ready."""
        try:
            # Test the LLM connection
            test_response = self.llm.invoke([HumanMessage(content="test")])
            return bool(test_response.content)
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get assistant statistics."""
        total_conversations = len(self.conversations)
        total_messages = sum(len(conv) for conv in self.conversations.values())
        
        return {
            "model_name": self.model_name,
            "active_conversations": total_conversations,
            "total_messages": total_messages,
            "max_context_messages": self.max_context_messages,
            "max_response_length": self.max_response_length,
            "framework": "LangChain",
            "server_agents_cached": len(self._server_agents),
            "available_servers": list(self._server_agents.keys()) if self._server_agents else []
        }