#!/usr/bin/env python3
"""Test script for the scraper module.

Usage:
    python -m tests.scrape_page <url>

Example:
    python -m tests.scrape_page https://example.com
"""

import sys

from src.message_processing.scraper import get_content


def test_scraper_with_url(url: str) -> None:
    """Test the scraper with a given URL and print the content."""
    print(f"Scraping URL: {url}")
    print("-" * 50)
    
    try:
        content = get_content(url)
        print("Scraped content:")
        print("=" * 50)
        print(content)
        print("=" * 50)
        print(f"Content length: {len(content)} characters")
        
    except Exception as e:
        print(f"Error scraping URL: {e}")
        sys.exit(1)


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) != 2:
        print("Usage: python -m tests.scrape_page <url>")
        print("Example: python -m tests.scrape_page https://example.com")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://")
        sys.exit(1)
    
    test_scraper_with_url(url)


if __name__ == "__main__":
    main()