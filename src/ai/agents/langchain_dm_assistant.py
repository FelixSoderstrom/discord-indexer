"""LangChain-based Discord DM Assistant.

Replaces the custom DMAssistant with a LangChain agent that provides
reliable tool calling, async execution, and better conversation management.
"""

import logging
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# Enable LangChain debugging when configured
try:
    from src.config.settings import settings
    if settings.LANGCHAIN_VERBOSE:
        import langchain
        langchain.debug = True
        langchain.verbose = True
        print("🐛 LangChain verbose mode enabled")
except ImportError:
    pass

from langchain_ollama import ChatOllama
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from src.ai.agents.tools.langchain_search_tool import create_server_specific_search_tool

try:
    from src.config.settings import settings
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
            else float(os.getenv("LLM_TEMPERATURE", "0.1"))
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
        self.max_agent_iterations = int(os.getenv("LLM_MAX_AGENT_ITERATIONS", "10"))
        self.max_execution_time = int(os.getenv("LLM_MAX_EXECUTION_TIME", "30"))
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize base LangChain components (agent will be created per-server)
        self._initialize_base_langchain()
        
        # Server-specific agents cache: server_id -> AgentExecutor
        self._user_server_agents: Dict[str, AgentExecutor] = {}  # Key: f"{user_id}:{server_id}"
    
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
            
        except (ImportError, ValueError, ConnectionError, RuntimeError, AttributeError) as e:
            self.logger.error(f"Failed to initialize base LangChain components: {e}")
            raise
    
    def _get_or_create_user_server_agent(self, user_id: str, server_id: str) -> AgentExecutor:
        """Get or create an agent executor bound to a specific user and server.
        
        Args:
            user_id: Discord user ID
            server_id: Discord server ID
            
        Returns:
            AgentExecutor configured for this user and server
        """
        # Check if we already have an agent for this user+server
        agent_key = f"{user_id}:{server_id}"
        if agent_key in self._user_server_agents:
            return self._user_server_agents[agent_key]
        
        try:
            # Create server-specific search tool (Discord messages)
            server_search_tool = create_server_specific_search_tool(server_id)
            
            server_tools = [server_search_tool]
            
            # Create agent for this user+server
            user_server_agent = create_tool_calling_agent(
                llm=self.llm,
                tools=server_tools,
                prompt=self.prompt
            )
            
            # Create agent executor
            agent_executor = AgentExecutor(
                agent=user_server_agent,
                tools=server_tools,
                verbose=True,
                max_iterations=self.max_agent_iterations,
                max_execution_time=self.max_execution_time,
                handle_parsing_errors=True
            )
            
            # Cache the agent executor
            self._user_server_agents[agent_key] = agent_executor
            
            self.logger.info(f"Created user-specific agent for user {user_id} in server {server_id}")
            return agent_executor
            
        except (ImportError, ValueError, ConnectionError, RuntimeError, AttributeError) as e:
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
Use the search_messages tool when users ask about past conversations or events in this Discord server."""
    
    
    async def respond_to_dm(
        self, 
        message: str, 
        user_id: str, 
        user_name: str = None, 
        server_id: str = None
    ) -> str:
        """Generate stateless response using LangChain agent.
        
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
            # Get user+server-specific agent executor
            agent_executor = self._get_or_create_user_server_agent(user_id, server_id)
            
            # Stateless conversation - no chat history
            chat_history = []
            
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
            
            # Log interaction
            user_display = user_name or user_id
            self.logger.info(f"LangChain DM response generated for {user_display}")
            
            return response_content
            
        except asyncio.TimeoutError:
            self.logger.error(f"LangChain agent timeout for user {user_id}")
            return "⏰ **Request Timeout**: Your request took too long to process. Please try a simpler question."
        
        except (ValueError, RuntimeError, ConnectionError, AttributeError) as e:
            self.logger.error(f"Error in LangChain DM response: {e}")
            return "❌ **Processing Error**: I encountered an issue while processing your message. Please try again."
    
    
    
    async def health_check_async(self, timeout_seconds: float = 60.0, quick_mode: bool = False) -> bool:
        """Check if the assistant is healthy and ready (async version).
        
        Args:
            timeout_seconds: Maximum time to wait for health check completion
            quick_mode: If True, only check server connectivity without model invocation
            
        Returns:
            True if the assistant is healthy and responsive, False otherwise
        """
        try:
            self.logger.info("🔍 Starting async LLM health check...")
            
            # First, do a quick Ollama server connectivity check
            self.logger.info("⚡ Checking Ollama server connectivity...")
            if not await self._check_ollama_server_async():
                self.logger.error("❌ Ollama server not accessible - ensure Ollama is running")
                return False
            
            self.logger.info("✅ Ollama server is accessible")
            
            # In quick mode, skip the model invocation test
            if quick_mode:
                self.logger.info("⚡ Quick mode enabled - skipping model invocation test")
                return True
            
            # Check if model is already loaded to set expectations
            from src.ai.utils import is_model_loaded
            model_already_loaded = await asyncio.get_running_loop().run_in_executor(
                None, is_model_loaded, self.model_name
            )
            
            if model_already_loaded:
                self.logger.info("🤖 Testing model responsiveness (model already loaded - should be fast)...")
            else:
                self.logger.info("🤖 Testing model responsiveness (triggering model load - may take 30-60s)...")
            
            loop = asyncio.get_running_loop()
            
            def _sync_health_check():
                """Internal synchronous health check for executor."""
                test_response = self.llm.invoke([HumanMessage(content="test")])
                return bool(test_response.content)
            
            # Run the synchronous health check in a thread pool with timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_health_check),
                timeout=timeout_seconds
            )
            
            if result:
                self.logger.info("✅ LLM health check passed - model is responsive")
            else:
                self.logger.error("❌ LLM health check failed - model returned empty response")
            
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(f"❌ LLM health check timed out after {timeout_seconds}s (likely model loading)")
            return False
        except (ValueError, RuntimeError, ConnectionError, AttributeError) as e:
            self.logger.error(f"❌ LLM health check failed: {e}")
            return False
    
    async def _check_ollama_server_async(self) -> bool:
        """Check if Ollama server is accessible (async version).
        
        Returns:
            True if Ollama server is accessible, False otherwise
        """
        try:
            # Use the existing Ollama client to do a lightweight server check
            from src.ai.utils import get_ollama_client
            
            loop = asyncio.get_running_loop()
            
            def _sync_server_check():
                """Internal sync check for Ollama server."""
                client = get_ollama_client()
                # Simple list models call to check server connectivity
                models = client.list()
                return bool(models.get("models"))
            
            # Run server check in executor with short timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_server_check),
                timeout=5.0
            )
            
            return result
            
        except (asyncio.TimeoutError, ConnectionError, OSError, ValueError, KeyError, RuntimeError) as e:
            self.logger.debug(f"Ollama server check failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get assistant statistics."""
        return {
            "model_name": self.model_name,
            "max_response_length": self.max_response_length,
            "framework": "LangChain",
            "mode": "stateless",
            "user_server_agents_cached": len(self._user_server_agents),
            "cached_user_server_pairs": list(self._user_server_agents.keys()) if self._user_server_agents else []
        }