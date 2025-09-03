"""Link and content extraction functionality for Discord messages.

Handles extraction and processing of URLs, mentions, attachments,
and other structured content from Discord messages.
"""

import logging
from typing import Dict, Any, List, Optional
import re

from src.message_processing.scraper import get_content
from src.exceptions.message_processing import MessageProcessingError


logger = logging.getLogger(__name__)


def extract_urls(message_content: str) -> List[str]:
    """Extract URLs from message content.
    
    Args:
        message_content: Raw text content from Discord message
        
    Returns:
        List of extracted URLs
    """
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, message_content)
    
    return urls


def extract_mentions(message_content: str) -> Dict[str, List[str]]:
    """Extract user and channel mentions from message content.
    
    Args:
        message_content: Raw text content from Discord message
        
    Returns:
        Dictionary containing user_mentions and channel_mentions lists
    """
    user_mentions = re.findall(r'<@!?(\d+)>', message_content)
    channel_mentions = re.findall(r'<#(\d+)>', message_content)
    
    return {
        'user_mentions': user_mentions,
        'channel_mentions': channel_mentions
    }


def analyze_link_content(url: str) -> Optional[Dict[str, Any]]:
    """Analyze and extract metadata from a URL.
    
    Args:
        url: URL to analyze and extract metadata from
        
    Returns:
        None until LinkAnalyzer agent is integrated
    """
    logger.info(f"Scraping content from URL: {url}")
    
    try:
        content = get_content(url)
        logger.info(f"Successfully scraped content from {url} ({len(content)} characters)")
    except RuntimeError as e:
        logger.warning(f"Failed to scrape content from {url}: {e}")
        raise MessageProcessingError()
    


    # =============================================================================
    # LINK ANALYZER INTEGRATION POINT - This is where the cleaned HTML is expected to be accessible
    # =============================================================================
    # Input: cleaned_html_content (string from scraper) - NOW AVAILABLE
    # LinkAnalyzer Process:
    #   1. Take cleaned HTML content (no HTML tags)
    #   2. Extract relevant content using LLM agent
    #   3. Return structured content in template format
    #
    # Example integration:
    # relevant_content: str = await agent.extract_relevant_content(cleaned_html_content)
    
    # =============================================================================
    # OUTPUT - This is where we have the relevant content (LLM output)
    # =============================================================================
    # The relevant_content string contains structured extracted information ready for:
    #   1. Embedding generation (in message_processing/embedding.py)
    #   2. Storage in ChromaDB with message metadata
    #   3. Future retrieval by other agents for question answering
    #
    # Expected relevant_content format:
    # Topic: [Main subject]
    # Type: [Content category] 
    # Summary: [2-3 sentence overview]
    # Key points: [3-5 brief bullet points]
    # Entities: [Important names/terms]
    
    # TODO: Integrate LinkAnalyzer agent to process cleaned_html_content
    # For now, return None until agent integration is complete
        


def process_message_extractions(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process all extraction requirements for a message.
    
    Coordinates URL extraction, mention extraction, and content analysis.
    
    Args:
        message_data: Complete message data dictionary
        
    Returns:
        Dictionary containing extraction results
    """
    
    extraction_results = {
        'urls': [],
        'mentions': {
            'user_mentions': [],
            'channel_mentions': []
        },
        'link_metadata': [],
        'extraction_metadata': {
            'urls_found': 0,
            'mentions_found': 0,
            'links_analyzed': 0
        }
    }
    
    message_content = message_data.get('content', '')
    
    if message_content:
        # Extract URLs
        urls = extract_urls(message_content)
        extraction_results['urls'] = urls
        extraction_results['extraction_metadata']['urls_found'] = len(urls)
        
        # Analyze each URL - NOT IMPLEMENTED
        for url in urls:
            link_analysis = analyze_link_content(url)
            if link_analysis:
                extraction_results['link_metadata'].append(link_analysis)
        
        extraction_results['extraction_metadata']['links_analyzed'] = len(extraction_results['link_metadata'])
        
        # Extract mentions
        mentions = extract_mentions(message_content)
        extraction_results['mentions'] = mentions
        total_mentions = len(mentions['user_mentions']) + len(mentions['channel_mentions'])
        extraction_results['extraction_metadata']['mentions_found'] = total_mentions
    
    return extraction_results

