"""LangChain tool for Discord message search using ChromaDB.

Wraps the existing SearchTool functionality in a LangChain tool decorator
for seamless integration with LangChain agents.
"""

import logging
from typing import List, Dict, Any
from langchain_core.tools import tool

from src.llm.agents.tools.search_tool import create_search_tool


logger = logging.getLogger(__name__)


def create_server_specific_search_tool(server_id: str):
    """Create a search tool that's hardcoded to a specific server.
    
    Args:
        server_id: Discord server ID to bind this tool to
        
    Returns:
        LangChain tool that can only search the specified server
    """
    @tool
    def search_messages(query: str, limit: int = 5) -> str:
        """Search Discord message history for relevant content.
        
        Use this tool when users ask about past conversations, specific topics,
        or what someone said about something. This tool searches THIS SERVER's
        message history using semantic similarity.
        
        Args:
            query: Search query (e.g., "standup meeting", "project deadline", "tetris")
            limit: Maximum number of results to return (default: 5, max: 10)
            
        Returns:
            Formatted string with search results including author, channel, timestamp, and content
        """
        try:
            # Create search tool for the bound server
            search_tool = create_search_tool(server_id)
            
            # Execute search
            results = search_tool.search_messages(query, limit)
            
            # Format results
            formatted_results = search_tool.format_search_results(results)
            
            logger.info(f"Server-bound search executed: query='{query}', server={server_id}, results={len(results)}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in server-bound search tool for server {server_id}: {e}")
            return f"Search failed: Unable to query message history for this server. Error: {str(e)}"
    
    # Update tool name and description to reflect server binding
    search_messages.name = "search_messages"
    search_messages.description = f"Search message history for this Discord server (ID: {server_id}). Use when users ask about past conversations or topics."
    
    return search_messages


@tool
def search_discord_messages(query: str, server_id: str, limit: int = 5) -> str:
    """Search Discord message history for relevant content.
    
    Use this tool when users ask about past conversations, specific topics,
    or what someone said about something. Searches the server's message history
    using semantic similarity.
    
    Args:
        query: Search query (e.g., "standup meeting", "project deadline", "Carl XVI Gustaf")
        server_id: Discord server ID to search within (REQUIRED - no default)
        limit: Maximum number of results to return (default: 5, max: 10)
        
    Returns:
        Formatted string with search results including author, channel, timestamp, and content
    """
    try:
        # Create search tool for the server
        search_tool = create_search_tool(server_id)
        
        # Execute search
        results = search_tool.search_messages(query, limit)
        
        # Format results
        formatted_results = search_tool.format_search_results(results)
        
        logger.info(f"LangChain search executed: query='{query}', server={server_id}, results={len(results)}")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error in LangChain search tool: {e}")
        return f"Search failed: Unable to query message history. Error: {str(e)}"


def get_search_tools(server_id: str) -> List:
    """Get list of search tools configured for the given server.
    
    Args:
        server_id: Discord server ID
        
    Returns:
        List of LangChain tools
    """
    # Create a partially applied version with server_id
    def server_search_tool(query: str, limit: int = 5) -> str:
        return search_discord_messages(query, server_id, limit)
    
    # Update the tool's metadata
    server_search_tool.name = "search_discord_messages"
    server_search_tool.description = f"""Search Discord message history for server {server_id}.
    
Use this when users ask about:
- Past conversations or discussions
- What someone said about a topic
- Specific events or announcements
- Project updates or deadlines

Args:
    query (str): Search query describing what to find
    limit (int): Number of results to return (default: 5, max: 10)

Returns:
    str: Formatted search results with author, channel, and message content
"""
    
    return [search_discord_messages]