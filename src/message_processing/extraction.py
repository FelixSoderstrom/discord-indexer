"""Link and content extraction functionality for Discord messages.

Handles extraction and processing of URLs, mentions, attachments,
and other structured content from Discord messages.
"""

import logging
from typing import Dict, Any, List, Optional
import re

from src.message_processing.scraper import get_content
from src.exceptions.message_processing import MessageProcessingError, LLMProcessingError
from src.llm.agents.link_analyzer import LinkAnalyzer


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


async def analyze_link_content(url: str) -> Optional[str]:
    """Analyze and extract summary from a URL.
    
    Args:
        url: URL to analyze and extract summary from
        
    Returns:
        LLM-generated summary string for embedding, None if processing fails
    """
    link_analyzer = LinkAnalyzer()
    logger.info(f"Scraping content from URL: {url}")
    
    try:
        content = get_content(url)
        logger.info(f"Successfully scraped content from {url} ({len(content)} characters)")
    except RuntimeError as e:
        logger.warning(f"Failed to scrape content from {url}: {e}")
        raise MessageProcessingError(f"Failed to scrape URL {url}: {e}")
    
    try:
        summary = await link_analyzer.extract_relevant_content(content)
        logger.info(f"Successfully extracted summary from {url} ({len(summary)} characters)")
        return summary
    except LLMProcessingError as e:
        logger.warning(f"Failed to extract content from {url} using LLM: {e}")
        raise LLMProcessingError(f"Failed to extract content from URL {url}: {e}")
        


async def process_message_extractions(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process all extraction requirements for a message.
    
    Coordinates URL extraction, mention extraction, and link content analysis.
    Generates summaries for embedding and stores URLs as metadata.
    
    Args:
        message_data: Complete message data dictionary
        
    Returns:
        Dictionary containing extraction results with summaries and metadata
    """
    
    extraction_results = {
        'urls': [],
        'mentions': {
            'user_mentions': [],
            'channel_mentions': []
        },
        'link_summaries_combined': '',  # Combined summaries for embedding
        'extraction_metadata': {
            'urls_found': 0,
            'mentions_found': 0,
            'links_analyzed': 0,
            'summaries_generated': 0
        }
    }
    
    message_content = message_data.get('content', '')
    
    if message_content:
        # Extract URLs
        urls = extract_urls(message_content)
        extraction_results['urls'] = urls
        extraction_results['extraction_metadata']['urls_found'] = len(urls)
        
        # Analyze each URL and collect summaries
        summaries = []
        for url in urls:
            try:
                summary = await analyze_link_content(url)
                if summary:
                    summaries.append(summary)
                    extraction_results['extraction_metadata']['summaries_generated'] += 1
                    logger.info(f"Generated summary for {url}")
            except MessageProcessingError as e:
                logger.warning(f"Skipping URL {url} due to processing error: {e}")
                continue
            except LLMProcessingError as e:
                logger.warning(f"Skipping URL {url} due to LLM processing error: {e}")
                continue
        
        # Combine all summaries with newlines for embedding
        if summaries:
            extraction_results['link_summaries_combined'] = '\n\n'.join(summaries)
            logger.info(f"Combined {len(summaries)} link summaries for embedding")
        
        extraction_results['extraction_metadata']['links_analyzed'] = len(summaries)
        
        # Extract mentions
        mentions = extract_mentions(message_content)
        extraction_results['mentions'] = mentions
        total_mentions = len(mentions['user_mentions']) + len(mentions['channel_mentions'])
        extraction_results['extraction_metadata']['mentions_found'] = total_mentions
    
    return extraction_results

