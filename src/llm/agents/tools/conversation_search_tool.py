"""LangChain tool for searching conversation history database.

Allows the LLM to search through its own conversation history with users
when they reference previous conversations or need context.
"""

import logging
from typing import List, Dict, Any
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_conversation_search_tool(user_id: str, server_id: str):
    """Create a conversation search tool for a specific user and server.
    
    Args:
        user_id: Discord user ID to search conversations for
        server_id: Discord server ID to bind this tool to
        
    Returns:
        LangChain tool that can search conversation history
    """
    @tool
    def search_conversation_history(query: str, limit: int = 10) -> str:
        """Search through previous conversations with this user.
        
        Use this tool when the user references previous conversations, says things
        like "remember when...", "you told me before...", or expects you to know
        something from past interactions.
        
        Args:
            query: Search terms to find relevant conversations
            limit: Maximum number of conversation messages to return (default 10)
            
        Returns:
            Formatted conversation history matching the search terms
        """
        try:
            from src.db.conversation_db import get_conversation_db
            
            # Get database instance
            conv_db = get_conversation_db()
            
            # Extract search terms from query
            search_terms = _extract_search_terms(query)
            
            if not search_terms:
                return "No valid search terms found. Please provide specific keywords to search for."
            
            # Search conversation history
            results = conv_db.search_conversation_history(
                user_id=user_id,
                server_id=server_id,
                query_terms=search_terms,
                limit=limit,
                days_back=90  # Search last 90 days
            )
            
            if not results:
                return f"No previous conversations found matching '{query}'. This might be the first time we've discussed this topic."
            
            # Format results for LLM
            formatted_results = []
            formatted_results.append(f"Found {len(results)} relevant conversation messages:")
            formatted_results.append("")
            
            for i, msg in enumerate(results, 1):
                role = "You" if msg["role"] == "assistant" else "User"
                timestamp = msg.get("timestamp", "unknown time")
                content = msg["content"]
                
                # Truncate very long messages
                if len(content) > 200:
                    content = content[:200] + "..."
                
                formatted_results.append(f"{i}. [{timestamp}] {role}: {content}")
            
            formatted_results.append("")
            formatted_results.append("Use this context to provide a more informed response.")
            
            logger.info(f"Conversation search found {len(results)} results for query: {query[:50]}...")
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            error_msg = f"Error searching conversation history: {str(e)}"
            logger.error(error_msg)
            return f"I'm sorry, I couldn't search our conversation history right now. {error_msg}"
    
    # Customize the tool description with user context
    search_conversation_history.description = f"Search through previous conversations with this user. Use when they reference past discussions or expect continuity from previous interactions."
    
    return search_conversation_history


def _extract_search_terms(query: str) -> List[str]:
    """Extract meaningful search terms from a query string."""
    import re
    
    # Remove common words
    stop_words = {
        'what', 'when', 'where', 'who', 'why', 'how', 'is', 'are', 'was', 'were',
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'about', 'did', 'do', 'does', 'can', 'could', 'would',
        'you', 'me', 'i', 'we', 'they', 'he', 'she', 'it', 'that', 'this'
    }
    
    # Extract words (alphanumeric, 3+ chars)
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]{2,}\b', query.lower())
    
    # Filter out stop words and return meaningful terms
    meaningful_terms = [word for word in words if word not in stop_words]
    return meaningful_terms[:5]  # Limit to top 5 terms