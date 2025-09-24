"""LangChain tool for searching user's conversation history with the assistant.

Provides access to the user's previous conversations with the AI assistant
for context-aware responses and continuity across stateless interactions.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool

from src.db.conversation_db import get_conversation_db


logger = logging.getLogger(__name__)


def create_conversation_search_tool(user_id: str, server_id: str):
    """Create a conversation search tool for a specific user and server.
    
    Args:
        user_id: Discord user ID
        server_id: Discord server ID (or "0" for DMs)
        
    Returns:
        LangChain tool that can search this user's conversation history
    """
    @tool
    def search_conversation_history(query_terms: str) -> str:
        """Search the user's conversation history with the assistant.
        
        Use this tool to find relevant context from previous conversations
        with this user. Helps provide continuity and reference past discussions.
        
        Args:
            query_terms: Space-separated search terms to find in conversation history
            limit: Maximum number of messages to return (default: 10)
            
        Returns:
            Formatted string with relevant conversation history
        """
        try:
            # Get conversation database
            conv_db = get_conversation_db()
            
            # Use "0" as server_id for DM contexts
            effective_server_id = server_id if server_id else "0"
            
            # Split query terms and search
            terms = query_terms.strip().split()
            if not terms:
                return "No search terms provided."
            
            # Search conversation history with fixed limit
            results = conv_db.search_conversation_history(
                user_id=user_id,
                server_id=effective_server_id,
                query_terms=terms,
                limit=15,
                days_back=90  # Search last 90 days
            )
            
            if not results:
                return "No relevant conversation history found."
            
            # Format results
            formatted_results = []
            formatted_results.append(f"Found {len(results)} relevant messages from conversation history:")
            formatted_results.append("")
            
            for msg in results:
                role_icon = "=d" if msg['role'] == 'user' else ">"
                timestamp = msg['timestamp'][:19] if msg['timestamp'] else "Unknown"
                content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
                
                formatted_results.append(f"{role_icon} {msg['role'].title()} [{timestamp}]:")
                formatted_results.append(f"   {content}")
                formatted_results.append("")
            
            result_text = "\n".join(formatted_results)
            
            logger.info(f"Conversation search executed: user={user_id}, server={effective_server_id}, terms={terms}, results={len(results)}")
            return result_text
            
        except (ConnectionError, TimeoutError, ValueError, KeyError, AttributeError, RuntimeError) as e:
            logger.error(f"Error in conversation search tool: {e}")
            return f"Search failed: Unable to query conversation history. Error: {str(e)}"
    
    # Update tool metadata
    search_conversation_history.name = "search_conversation_history"
    search_conversation_history.description = f"Search conversation history between user {user_id} and the assistant for context and continuity."
    
    return search_conversation_history


@tool
def search_user_conversation_history(user_id: str, server_id: str, query_terms: str) -> str:
    """Search a user's conversation history with the assistant.
    
    Use this tool to find relevant context from previous conversations
    with the specified user. Helps provide continuity across stateless interactions.
    
    Args:
        user_id: Discord user ID
        server_id: Discord server ID (use "0" for DMs)
        query_terms: Space-separated search terms
        limit: Maximum number of messages to return (default: 10)
        
    Returns:
        Formatted string with relevant conversation history
    """
    try:
        # Get conversation database
        conv_db = get_conversation_db()
        
        # Split query terms and search
        terms = query_terms.strip().split()
        if not terms:
            return "No search terms provided."
        
        # Search conversation history with fixed limit
        results = conv_db.search_conversation_history(
            user_id=user_id,
            server_id=server_id,
            query_terms=terms,
            limit=15,
            days_back=90  # Search last 90 days
        )
        
        if not results:
            return "No relevant conversation history found."
        
        # Format results
        formatted_results = []
        formatted_results.append(f"Found {len(results)} relevant messages from conversation history:")
        formatted_results.append("")
        
        for msg in results:
            role_icon = "=d" if msg['role'] == 'user' else ">"
            timestamp = msg['timestamp'][:19] if msg['timestamp'] else "Unknown"
            content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
            
            formatted_results.append(f"{role_icon} {msg['role'].title()} [{timestamp}]:")
            formatted_results.append(f"   {content}")
            formatted_results.append("")
        
        result_text = "\n".join(formatted_results)
        
        logger.info(f"Conversation search executed: user={user_id}, server={server_id}, terms={terms}, results={len(results)}")
        return result_text
        
    except (ConnectionError, TimeoutError, ValueError, KeyError, AttributeError, RuntimeError) as e:
        logger.error(f"Error in conversation search tool: {e}")
        return f"Search failed: Unable to query conversation history. Error: {str(e)}"