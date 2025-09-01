"""
Simple test script for LinkAnalyzer agent.
Tests content extraction from cleaned HTML documents.

`python -m tests.link_analyzer_test` from root directory
"""

import asyncio


from src.llm.agents.link_analyzer import LinkAnalyzer


async def test_link_analyzer():
    """Test the LinkAnalyzer with mock cleaned HTML content."""
    
    # Mock cleaned HTML content (replace with your own test data)
    # This represents HTML content with all tags removed
    mock_cleaned_html = """
    How to Build a REST API with Python and Flask
    
    A Complete Tutorial for Beginners
    
    In this comprehensive guide, we'll walk through building a RESTful API using Python and Flask. 
    This tutorial is perfect for developers who want to learn backend development.
    
    What You'll Learn:
    Getting started with Flask framework
    Setting up your development environment
    Creating API endpoints
    Handling HTTP requests and responses
    Database integration with SQLAlchemy
    Authentication and security best practices
    Testing your API
    
    Prerequisites:
    Basic Python knowledge
    Understanding of HTTP methods
    Familiarity with JSON format
    
    Let's start by installing Flask using pip install flask. Once installed, you can create 
    your first application by importing Flask and creating an app instance.
    
    The Flask framework makes it easy to create web applications and APIs. With just a few 
    lines of code, you can have a working API endpoint that responds to HTTP requests.
    
    Remember to always validate user input and implement proper error handling in your 
    production applications. Security should be a top priority when building APIs that 
    will be accessed over the internet.
    
    Flask SQLAlchemy ORM Python REST API Tutorial Backend Development
    
    Published by TechBlog on March 15, 2024
    """
    
    print("=== LinkAnalyzer Test ===")
    print(f"Input HTML length: {len(mock_cleaned_html)} characters")
    print("\nInitializing LinkAnalyzer...")
    
    try:
        # Initialize the analyzer
        analyzer = LinkAnalyzer()
        
        print("LinkAnalyzer initialized successfully!")
        print(f"Using model: {analyzer.model_name}")
        print(f"Temperature: {analyzer.temperature}")
        
        print("\nExtracting content...")
        
        # Extract relevant content
        result = await analyzer.extract_relevant_content(mock_cleaned_html)
        
        print("\n" + "="*50)
        print("EXTRACTED CONTENT:")
        print("="*50)
        print(result)
        print("="*50)
        
        print(f"\nExtraction completed successfully!")
        print(f"Output length: {len(result)} characters")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_link_analyzer())
