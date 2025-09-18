import logging
import os
from typing import Dict, Optional

from src.llm.chat_completion import generate_completion_with_messages_async, LLMResponse
from src.llm.utils import ensure_model_available, health_check
from src.config.settings import settings
from src.exceptions.message_processing import LLMProcessingError


class LinkAnalyzer:
    """
    Stateless agent for extracting relevant content from cleaned HTML documents
    """
    
    def __init__(
        self,
        model_name: str = None,
        temperature: float = None
    ):
        """
        Initialize the Link Analyzer
        
        Args:
            model_name: Ollama model name
            temperature: Generation temperature
        """
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.temperature = (
            temperature 
            if temperature is not None 
            else float(os.getenv("LLM_TEMPERATURE", "0.3"))
        )
        
        self.logger = logging.getLogger(__name__)
        
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
                "link_analyzer.txt"
            )
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError as e:
            self.logger.error(f"Error loading system prompt: {e}")
            # Fallback system prompt
            return "You are a content extraction specialist. Extract relevant information from HTML content."
    
    async def extract_relevant_content(self, cleaned_html: str) -> str:
        """
        Extract relevant content from cleaned HTML document
        
        Args:
            cleaned_html: HTML document with tags removed
            
        Returns:
            Structured content string in specified template format
            
        Raises:
            Exception: If content extraction fails completely
        """
        try:
            # Validate input
            if not cleaned_html or not cleaned_html.strip():
                raise LLMProcessingError("Empty or whitespace-only HTML content provided")
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Extract relevant content from this cleaned HTML:\n\n{cleaned_html}"}
            ]
            
            # Generate response using chat completion API with token limit
            llm_response = await generate_completion_with_messages_async(
                messages=messages,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=500  # Enforce 500 token limit in code
            )
            
            if not llm_response.success:
                self.logger.error(f"LLM generation failed: {llm_response.error}")
                raise LLMProcessingError(f"Content extraction failed: {llm_response.error}")

            extracted_content = llm_response.content.strip()

            # Validate that we got some content
            if not extracted_content:
                raise LLMProcessingError("LLM returned empty content")
            
            # Log the extraction
            self.logger.info(
                f"Content extracted successfully "
                f"({llm_response.tokens_used} tokens, {llm_response.response_time:.2f}s)"
            )
            
            return extracted_content
            
        except ValueError as e:
            self.logger.error(f"Input validation error: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check if the analyzer is healthy and ready"""
        return health_check(self.model_name)
    
    def get_stats(self) -> Dict:
        """Get analyzer statistics"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": 500,
            "agent_type": "link_analyzer"
        }
