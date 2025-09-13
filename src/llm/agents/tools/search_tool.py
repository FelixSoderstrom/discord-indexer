"""Search tool for DMAssistant to query Discord message history.

Provides ChromaDB search functionality scoped to specific servers
for finding relevant messages in conversation context.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from src.db.setup_db import get_db
except ImportError:
    # Fallback for testing
    from src.db.setup_db import get_db


logger = logging.getLogger(__name__)


class SearchTool:
    """Tool for searching Discord message history using ChromaDB."""
    
    def __init__(self, server_id: str):
        """Initialize search tool for specific server.
        
        Args:
            server_id: Discord server ID to search within
        """
        self.server_id = server_id
        self.max_results = 10
        
    def search_messages(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for messages relevant to the query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of relevant message dictionaries
        """
        if not query.strip():
            logger.warning("Empty search query provided")
            return []
        
        try:
            # Get ChromaDB client for this server
            client = get_db(int(self.server_id))
            
            # Get the messages collection
            collection = client.get_or_create_collection(
                name="messages",
                metadata={"server_id": self.server_id}
            )
            
            # Search for similar messages
            results = collection.query(
                query_texts=[query],
                n_results=min(limit, self.max_results),
                include=['documents', 'metadatas', 'distances']
            )
            
            # Format results for DMAssistant
            formatted_results = []
            
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    formatted_results.append({
                        'content': doc,
                        'author': metadata.get('author_name', 'Unknown'),
                        'channel': metadata.get('channel_name', 'Unknown'),
                        'timestamp': metadata.get('timestamp', ''),
                        'relevance_score': round(1.0 - distance, 3)  # Convert distance to relevance
                    })
            
            logger.debug(f"Found {len(formatted_results)} results for query: {query[:50]}")
            return formatted_results
            
        except (ConnectionError, TimeoutError, ValueError, KeyError, AttributeError, RuntimeError) as e:
            logger.error(f"Error searching messages for server {self.server_id}: {e}")
            return []
    
    def get_tool_description(self) -> str:
        """Get description of this tool for LLM usage.
        
        Returns:
            Tool description string
        """
        return f"""
search_messages: Search Discord message history for relevant content
- Use this when users ask about past conversations or specific topics
- Query should be descriptive (e.g., "standup meeting", "project deadline", "bug report")
- Returns up to {self.max_results} most relevant messages with author and timestamp
- Only searches messages from this Discord server
"""
    
    def format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for display in conversation.
        
        Args:
            results: Search results from search_messages()
            
        Returns:
            Formatted string for inclusion in response
        """
        if not results:
            return "No relevant messages found in the server history."
        
        formatted = "Here's what I found in the message history:\n\n"
        
        for i, result in enumerate(results, 1):
            author = result['author']
            channel = result['channel']
            timestamp = result.get('timestamp', '')
            content = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
            
            formatted += f"**{i}. {author}** in #{channel}"
            if timestamp:
                try:
                    # Try to format timestamp nicely
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted += f" ({dt.strftime('%Y-%m-%d %H:%M')})"
                except:
                    pass
            
            formatted += f"\n> {content}\n\n"
        
        return formatted


def create_search_tool(server_id: str) -> SearchTool:
    """Create a SearchTool instance for the given server.
    
    Args:
        server_id: Discord server ID
        
    Returns:
        SearchTool instance
    """
    return SearchTool(server_id)