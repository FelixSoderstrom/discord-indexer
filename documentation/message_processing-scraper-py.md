# message_processing/scraper.py

## Overview

The `scraper.py` module provides web content extraction functionality using the trafilatura library. It orchestrates the process of fetching web pages and extracting clean, human-readable text content while removing HTML tags, headers, footers, navigation elements, and other non-essential content.

## Purpose

This module is designed to extract meaningful text content from web URLs for indexing and processing within the Discord-Indexer system. It focuses on retrieving only the main content that a human reader would find relevant, making it suitable for semantic search and LLM processing.

## Dependencies

- **trafilatura==2.0.0**: Primary web scraping and content extraction library
- **lxml_html_clean**: Required for HTML cleaning functionality (trafilatura dependency)
- **logging**: Error logging and debugging
- **re**: Regular expression operations for text cleaning

## Functions

### `get_content(url: str) -> str`

**Purpose**: Main orchestration function that coordinates the entire scraping process.

**Parameters**:
- `url` (str): The target URL to scrape content from

**Returns**:
- `str`: Clean, extracted text content from the webpage

**Behavior**:
1. Calls `_scrape_page()` to fetch raw HTML content
2. Calls `_clean_page()` to extract and clean the main content
3. Returns the final processed text

**Error Handling**: Propagates exceptions from underlying functions, causing application termination.

### `_scrape_page(url: str) -> str`

**Purpose**: Fetches raw HTML content from the specified URL using trafilatura.

**Parameters**:
- `url` (str): The target URL to fetch

**Returns**:
- `str`: Raw HTML content of the webpage

**Implementation Details**:
- Uses `trafilatura.fetch_url()` for HTTP requests
- Implements robust error checking for failed requests
- Logs errors before raising exceptions

**Error Conditions**:
- Network connectivity issues
- Invalid URLs
- HTTP errors (404, 500, etc.)
- Timeout errors

**Error Handling**: Logs error details and raises `RuntimeError` to crash the application.

### `_clean_page(html_content: str, url: str) -> str`

**Purpose**: Extracts main content from HTML and performs additional text cleaning.

**Parameters**:
- `html_content` (str): Raw HTML content from the webpage
- `url` (str): Original URL (used by trafilatura for context-aware extraction)

**Returns**:
- `str`: Clean, human-readable text content

**Content Extraction**:
- Uses `trafilatura.extract()` to remove HTML tags, headers, footers, navigation, ads, and other non-essential elements
- Focuses on main article/content text that humans would read
- Preserves text structure and formatting where appropriate

**Additional Cleaning**:
- Strips leading/trailing whitespace
- Normalizes excessive line breaks (`\n\s*\n` → `\n\n`)
- Normalizes spaces and tabs (`[ \t]+` → single space)

**Error Handling**: Logs extraction failures and raises `RuntimeError` for application termination.

## Error Handling Strategy

The module follows the project's error handling guidelines:

- **Specific Exception Catching**: Catches individual exceptions rather than broad `Exception` handlers
- **Logging**: All errors are logged using the module logger before raising
- **Application Termination**: Raises `RuntimeError` exceptions to crash the application when errors occur
- **No Silent Failures**: All error conditions result in logged messages and application termination

## Usage Examples

### Basic Usage
```python
from message_processing.scraper import get_content

# Extract content from a URL
content = get_content("https://example.com/article")
print(content)
```

### Integration with Message Processing
```python
# Typical usage within the message processing pipeline
url = "https://news.example.com/breaking-news"
try:
    extracted_text = get_content(url)
    # Process extracted_text for embedding generation
except RuntimeError as e:
    # Application will terminate, error is already logged
    pass
```

## Testing

The module includes a test script at `tests/scrape_page.py` for manual testing:

```bash
# Test with any URL
python -m tests.scrape_page https://example.com
```

The test script:
- Takes URLs via command line arguments
- Prints the full extracted content
- Shows content length statistics
- Handles errors gracefully with helpful messages

## Implementation Notes

### Trafilatura Configuration
- Uses standard `trafilatura.fetch_url()` and `trafilatura.extract()` functions
- The `url` parameter in `extract()` provides context for better content detection
- No custom configuration or fallback options are currently implemented

### Content Quality
- Trafilatura automatically handles most content extraction challenges
- The additional cleaning step normalizes whitespace for consistent formatting
- Content structure is preserved while removing visual formatting elements

### Performance Considerations
- Network requests are synchronous and blocking
- No caching is implemented
- No retry logic for failed requests
- Memory usage scales with webpage size

## Future Enhancements

Potential improvements for the scraper module:

1. **Caching**: Implement URL-based caching to avoid re-scraping
2. **Retry Logic**: Add exponential backoff for transient network failures
3. **Timeout Configuration**: Make request timeouts configurable
4. **Content Validation**: Add minimum content length validation
5. **User Agent Rotation**: Implement user agent rotation for better success rates
6. **Parallel Processing**: Support batch URL processing

## Integration Points

This module integrates with:

- **Message Processing Pipeline**: Extracts content from URLs found in Discord messages
- **Embedding Generation**: Provides clean text for vector embedding creation
- **Storage System**: Extracted content is stored alongside message metadata
- **Logging System**: Uses the centralized logging configuration
