import logging
import os
from typing import Dict, Optional, Any

from src.ai.utils import health_check, generate_image_description_async
from src.ai.model_manager import ModelManager
from src.exceptions.message_processing import LLMProcessingError

try:
    from src.config.settings import settings
except ImportError:
    # Fallback for direct script execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from src.config.settings import settings


class ImageAnalyzer:
    """
    Stateless agent for analyzing images and extracting structured descriptions
    
    Uses vision model to process images and return standardized format with
    subject, description, details, text, and context information.
    """
    
    def __init__(
        self,
        model_manager: ModelManager = None,
        temperature: float = None
    ):
        """
        Initialize the Image Analyzer
        
        Args:
            model_manager: ModelManager instance for vision model access
            temperature: Generation temperature for vision model
        """
        self.model_manager = model_manager or ModelManager()
        self.model_name = self.model_manager.get_vision_model()
        self.temperature = (
            temperature 
            if temperature is not None 
            else float(os.getenv("LLM_TEMPERATURE", "0.1"))
        )
        
        self.logger = logging.getLogger(__name__)
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from text file"""
        try:
            prompt_file = os.path.join(
                os.path.dirname(__file__), 
                "sys_prompts", 
                "image_analyzer.txt"
            )
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError as e:
            self.logger.error(f"Error loading system prompt: {e}")
            # Fallback system prompt
            return ("You are an image analyzer. Analyze images and provide structured "
                    "descriptions with subject, description, details, text, and context.")
    
    async def describe_image_async(self, image_data: bytes) -> str:
        """
        Generate structured description of image content
        
        Args:
            image_data: Raw image bytes to analyze
            
        Returns:
            Structured image description in standardized format:
            - Subject: {Main visual elements}
            - Description: {2-3 sentences describing the scene}  
            - Details: {2-3 bullet points of notable elements}
            - Text: {Any visible text in the image}
            - Context: {Setting/environment type}
            
        Raises:
            LLMProcessingError: If image analysis fails completely
        """
        try:
            # Validate input
            if not image_data or len(image_data) == 0:
                raise LLMProcessingError("Empty or invalid image data provided")
            
            self.logger.debug(f"Analyzing image using {self.model_name}")
            
            # Generate image description using async utils function
            result = await generate_image_description_async(
                image_data=image_data,
                prompt=self.system_prompt,
                model_name=self.model_name
            )
            
            if not result['success']:
                self.logger.error(f"Vision model generation failed: {result['error']}")
                raise LLMProcessingError(f"Image analysis failed: {result['error']}")
            
            description = result['content'].strip()
            
            # Validate that we got some content
            if not description:
                raise LLMProcessingError("Vision model returned empty description")
            
            # Log the analysis
            self.logger.info(
                f"Image analyzed successfully "
                f"({result['tokens_used']} tokens, {result['response_time']:.2f}s)"
            )
            
            return description
            
        except ValueError as e:
            self.logger.error(f"Input validation error: {e}")
            raise LLMProcessingError(f"Invalid image data: {e}")
        except (ConnectionError, TimeoutError, OSError, KeyError, RuntimeError) as e:
            self.logger.error(f"Vision model error: {e}")
            raise LLMProcessingError(f"Image analysis failed: {e}")
    
    def describe_image_sync(self, image_data: bytes) -> str:
        """
        Generate structured description of image content (synchronous version)
        
        Args:
            image_data: Raw image bytes to analyze
            
        Returns:
            Structured image description in standardized format
            
        Raises:
            LLMProcessingError: If image analysis fails completely
        """
        try:
            # Import sync vision function
            from src.ai.utils import generate_image_description_sync
            
            # Validate input
            if not image_data or len(image_data) == 0:
                raise LLMProcessingError("Empty or invalid image data provided")
            
            self.logger.debug(f"Analyzing image using {self.model_name} (sync)")
            
            # Generate image description using sync utils function  
            result = generate_image_description_sync(
                image_data=image_data,
                prompt=self.system_prompt,
                model_name=self.model_name
            )
            
            if not result['success']:
                self.logger.error(f"Vision model generation failed: {result['error']}")
                raise LLMProcessingError(f"Image analysis failed: {result['error']}")
            
            description = result['content'].strip()
            
            # Validate that we got some content
            if not description:
                raise LLMProcessingError("Vision model returned empty description")
            
            # Log the analysis
            self.logger.info(
                f"Image analyzed successfully "
                f"({result['tokens_used']} tokens, {result['response_time']:.2f}s)"
            )
            
            return description
            
        except ValueError as e:
            self.logger.error(f"Input validation error: {e}")
            raise LLMProcessingError(f"Invalid image data: {e}")
        except (ConnectionError, TimeoutError, OSError, KeyError, RuntimeError) as e:
            self.logger.error(f"Vision model error: {e}")
            raise LLMProcessingError(f"Image analysis failed: {e}")
    
    def health_check(self) -> bool:
        """Check if the analyzer is healthy and ready"""
        return health_check(self.model_name)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "agent_type": "image_analyzer",
            "vision_model": True,
            "output_format": "structured_description"
        }