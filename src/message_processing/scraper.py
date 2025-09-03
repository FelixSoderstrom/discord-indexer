import logging
import re
from typing import Optional

import trafilatura

logger = logging.getLogger(__name__)


def get_content(url: str) -> str:
    """Orchestrates the scraping process for a given URL"""
    html_content = _scrape_page(url)
    content = _clean_page(html_content, url)
    return content

def _scrape_page(url: str) -> str:
    """Scrapes the page for the given URL using trafilatura"""
    try:
        # Use standard trafilatura API
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.error(f"Failed to fetch URL: {url}")
            raise RuntimeError(f"Failed to fetch URL: {url}")
        
        return downloaded
        
    except Exception as e:
        logger.error(f"Error scraping page {url}: {e}")
        raise RuntimeError(f"Error scraping page {url}: {e}")

def _clean_page(html_content: str, url: str) -> str:
    """Extracts and cleans main content from HTML using trafilatura"""
    if not html_content:
        return ""
    
    try:
        # Use trafilatura.extract() to get clean main content
        extracted_content = trafilatura.extract(html_content, url=url)
        if not extracted_content:
            logger.error(f"Failed to extract content from HTML for URL: {url}")
            raise RuntimeError(f"Failed to extract content from HTML for URL: {url}")
        
        # Minimal additional cleaning
        cleaned_content = extracted_content.strip()
        
        # Remove excessive whitespace and normalize line breaks
        cleaned_content = re.sub(r'\n\s*\n', '\n\n', cleaned_content)
        cleaned_content = re.sub(r'[ \t]+', ' ', cleaned_content)
        
        return cleaned_content
        
    except Exception as e:
        logger.error(f"Error cleaning content for URL {url}: {e}")
        raise RuntimeError(f"Error cleaning content for URL {url}: {e}")