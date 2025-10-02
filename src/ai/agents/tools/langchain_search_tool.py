"""LangChain tool for Discord message search using ChromaDB.

Wraps the existing SearchTool functionality in a LangChain tool decorator
for seamless integration with LangChain agents.
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool

from src.ai.agents.tools.search_tool import create_search_tool


logger = logging.getLogger(__name__)


def create_server_specific_search_tool(server_id: str):
    """Create a search tool that's hardcoded to a specific server.
    
    Args:
        server_id: Discord server ID to bind this tool to
        
    Returns:
        LangChain tool that can only search the specified server
    """
    @tool
    def search_messages(query: str) -> str:
        """Search Discord message history for relevant content.
        
        Use this tool when users ask about past conversations, specific topics,
        or what someone said about something. This tool searches THIS SERVER's
        message history using semantic similarity.
        
        IMPORTANT: Results will show users by their display names (friendly names) 
        rather than technical usernames. You can search using any name variation
        (display name, username, nickname) and find the same user's messages.
        
        Args:
            query: Search query (e.g., "standup meeting", "project deadline", "John Doe messages", "what did sarah say about")
            
        Returns:
            Formatted string with search results including author display name, channel, timestamp, and content
        """
        try:
            # Create search tool for the bound server
            search_tool = create_search_tool(server_id)
            
            # Execute search with fixed limit (reduced to 5 for small model optimization)
            results = search_tool.search_messages(query, 5)
            
            # Format results
            formatted_results = search_tool.format_search_results(results)
            
            logger.info(f"Server-bound search executed: query='{query}', server={server_id}, results={len(results)}")
            return formatted_results
            
        except (ConnectionError, TimeoutError, ValueError, KeyError, AttributeError, RuntimeError) as e:
            logger.error(f"Error in server-bound search tool for server {server_id}: {e}")
            return f"Search failed: Unable to query message history for this server. Error: {str(e)}"
    
    # Update tool name and description to reflect server binding
    search_messages.name = "search_messages"
    search_messages.description = f"Search message history for this Discord server (ID: {server_id}). Use when users ask about past conversations or topics."
    
    return search_messages


