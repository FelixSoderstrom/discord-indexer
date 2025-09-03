#!/usr/bin/env python3
"""Test script to scrape URL and analyze with LLM.

Usage: python -m tests.scrape_and_analyze <URL>
"""

import sys
import asyncio

from src.message_processing.extraction import analyze_link_content


async def main():
    """Main test function."""
    if len(sys.argv) != 2:
        print("Usage: python scrape_and_analyze.py <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print(f"🔗 Scraping and analyzing: {url}")
    print("=" * 50)
    
    try:
        # Use existing link analyzer flow from pipeline
        llm_output = await analyze_link_content(url)
        
        print("📄 LLM Analysis Result:")
        print("-" * 30)
        print(llm_output)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
