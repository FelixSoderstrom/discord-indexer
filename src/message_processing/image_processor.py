import logging
import requests
import aiohttp
import asyncio
from typing import List, Optional
from io import BytesIO
from PIL import Image

from src.ai.model_manager import ModelManager
from src.exceptions.message_processing import MessageProcessingError
from src.config.settings import settings

logger = logging.getLogger(__name__)

class ImageProcessor:
    """
    Handles image processing for Discord messages using dedicated vision model.
    Downloads images from Discord CDN and generates text descriptions using the
    vision model specified in settings.VISION_MODEL_NAME.
    """
    
    def __init__(self, model_manager: Optional[ModelManager] = None):
        """
        Initialize the image processor.
        
        Args:
            model_manager: ModelManager instance to ensure vision model is loaded.
                          If None, creates a new instance which will load both models.
        """
        self.model_manager = model_manager or ModelManager()
        self.model_name = self.model_manager.get_vision_model()
        
    async def download_image_from_url(self, url: str) -> bytes:
        """
        Download image from Discord CDN URL asynchronously.
        
        Args:
            url: Discord CDN URL for the image
            
        Returns:
            Image data as bytes
            
        Raises:
            MessageProcessingError: If image download fails
        """
        try:
            logger.debug(f"Downloading image from URL: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '')
                    if not content_type.startswith('image/'):
                        raise MessageProcessingError(f"URL does not point to an image: {content_type}")
                    
                    # Read image data with size limit (10MB)
                    image_data = BytesIO()
                    total_size = 0
                    max_size = 10 * 1024 * 1024  # 10MB
                    
                    async for chunk in response.content.iter_chunked(8192):
                        total_size += len(chunk)
                        if total_size > max_size:
                            raise MessageProcessingError(f"Image too large: {total_size} bytes")
                        image_data.write(chunk)
                    
                    image_bytes = image_data.getvalue()
                    logger.debug(f"Successfully downloaded image: {len(image_bytes)} bytes")
                    return image_bytes
                    
        except aiohttp.ClientError as e:
            raise MessageProcessingError(f"Failed to download image from {url}: {str(e)}")
        except Exception as e:
            raise MessageProcessingError(f"Unexpected error downloading image: {str(e)}")
    
    def validate_image_format(self, image_data: bytes) -> bool:
        """
        Validate that image data is in a supported format.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            True if image format is supported
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Check if format is supported by most vision models
                supported_formats = {'JPEG', 'PNG', 'GIF', 'BMP', 'WEBP'}
                return img.format in supported_formats
        except Exception:
            return False
    
    async def generate_image_description(self, image_data: bytes) -> str:
        """Generate text description of image using ImageAnalyzer agent asynchronously."""
        try:
            if not self.validate_image_format(image_data):
                raise MessageProcessingError("Unsupported image format")
            
            logger.debug(f"Generating description for image using ImageAnalyzer")
            
            # Use ImageAnalyzer agent for consistent image processing
            from src.ai.agents.image_analyzer import ImageAnalyzer
            analyzer = ImageAnalyzer(model_manager=self.model_manager)
            
            description = await analyzer.describe_image_async(image_data)
            
            logger.debug(f"Generated image description: {description[:100]}...")
            return description
            
        except Exception as e:
            if isinstance(e, MessageProcessingError):
                raise
            raise MessageProcessingError(f"Failed to generate image description: {str(e)}")
    
    async def process_message_images(self, attachments: List[str]) -> str:
        """Process all images in a message and return combined descriptions asynchronously."""
        if not attachments:
            return ""
        
        descriptions = []
        processed_count = 0
        
        for i, url in enumerate(attachments):
            try:
                logger.debug(f"Processing image {i+1}/{len(attachments)}: {url}")
                
                # Download and process image (both now async)
                image_data = await self.download_image_from_url(url)
                description = await self.generate_image_description(image_data)
                
                # Format description with image number if multiple images
                if len(attachments) > 1:
                    descriptions.append(f"Image {i+1}: {description}")
                else:
                    descriptions.append(description)
                
                processed_count += 1
                
            except MessageProcessingError as e:
                logger.warning(f"Failed to process image {i+1}: {e}")
                continue
        
        if not descriptions:
            raise MessageProcessingError("Failed to process any images in message")
        
        combined_description = " ".join(descriptions)
        logger.info(f"Successfully processed {processed_count}/{len(attachments)} images")
        
        return combined_description


async def process_message_images(attachments: List[str]) -> str:
    """Main async function to process images in a Discord message."""
    if not attachments:
        return ""
    
    processor = ImageProcessor()
    return await processor.process_message_images(attachments)