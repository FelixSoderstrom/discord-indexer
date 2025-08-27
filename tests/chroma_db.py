#!/usr/bin/env python3
"""Interactive ChromaDB query test tool.

Allows selection of available server databases and querying for top results.
Run from terminal to interactively browse and query your Discord message databases.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.setup_db import list_server_databases, get_server_db
from chromadb.errors import ChromaError


# Setup logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise for interactive use
logger = logging.getLogger(__name__)


def display_available_databases() -> List[int]:
    """Display available database options and return server IDs.
    
    Returns:
        List of available server IDs
    """
    server_ids = list_server_databases()
    
    if not server_ids:
        print("❌ No databases found in src/db/")
        print("   Databases should be located at src/db/{server_id}/")
        return []
    
    print(f"📁 Found {len(server_ids)} database(s):")
    print()
    
    for i, server_id in enumerate(server_ids, 1):
        print(f"  {i}. Server ID: {server_id}")
    
    print()
    return server_ids


def get_user_selection(server_ids: List[int]) -> Optional[int]:
    """Get user's database selection from terminal input.
    
    Args:
        server_ids: List of available server IDs
        
    Returns:
        Selected server ID or None if invalid selection
    """
    while True:
        try:
            choice = input(f"Select database (1-{len(server_ids)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
                
            choice_num = int(choice)
            if 1 <= choice_num <= len(server_ids):
                return server_ids[choice_num - 1]
            else:
                print(f"❌ Please enter a number between 1 and {len(server_ids)}")
                
        except ValueError:
            print("❌ Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return None


def display_collection_info(db_client, server_id: int) -> List[str]:
    """Display information about collections in the database.
    
    Args:
        db_client: ChromaDB client instance
        server_id: Server ID for context
        
    Returns:
        List of collection names
    """
    try:
        collections = db_client.list_collections()
        
        if not collections:
            print(f"📂 No collections found in database for server {server_id}")
            return []
        
        print(f"📊 Collections in server {server_id} database:")
        print()
        
        collection_names = []
        for collection in collections:
            count = collection.count()
            print(f"  • {collection.name}: {count} documents")
            collection_names.append(collection.name)
        
        print()
        return collection_names
        
    except ChromaError as e:
        print(f"❌ Error accessing database collections: {e}")
        return []


def query_database_top_results(db_client, server_id: int, query_text: str = None) -> None:
    """Query database and display top 3 results.
    
    Args:
        db_client: ChromaDB client instance  
        server_id: Server ID for context
        query_text: Optional query text, if None will prompt user
    """
    try:
        # Get main messages collection
        collection_name = f"messages_{server_id}"
        
        try:
            collection = db_client.get_collection(name=collection_name)
        except (ValueError, ChromaError):
            print(f"❌ Messages collection '{collection_name}' not found")
            return
        
        # Get query from user if not provided
        if query_text is None:
            print("🔍 Enter your search query:")
            query_text = input("Query: ").strip()
            
            if not query_text:
                print("❌ Empty query, using default search...")
                query_text = "discord"
        
        print(f"\n🔎 Searching for: '{query_text}'")
        print("=" * 50)
        
        # Perform similarity search
        results = collection.query(
            query_texts=[query_text],
            n_results=3
        )
        
        if not results['documents'] or not results['documents'][0]:
            print("🔍 No results found for your query")
            return
        
        documents = results['documents'][0]
        metadatas = results['metadatas'][0] if results['metadatas'] else []
        distances = results['distances'][0] if results['distances'] else []
        
        print(f"📋 Top {len(documents)} results:\n")
        
        for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances), 1):
            print(f"🏆 Result #{i}")
            print(f"   Similarity: {1 - distance:.3f}" if distance is not None else "   Similarity: N/A")
            
            if metadata:
                author = metadata.get('author_name', 'Unknown')
                timestamp = metadata.get('timestamp', 'Unknown')
                msg_id = metadata.get('message_id', 'Unknown')
                
                print(f"   Author: {author}")
                print(f"   Time: {timestamp}")
                print(f"   Message ID: {msg_id}")
            
            # Truncate long messages for display
            display_content = doc[:200] + "..." if len(doc) > 200 else doc
            print(f"   Content: {display_content}")
            print()
        
    except ChromaError as e:
        print(f"❌ Database query error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error during query: {e}")


def run_interactive_query() -> None:
    """Main interactive query interface."""
    print("🤖 Discord Indexer - Database Query Tool")
    print("=" * 45)
    print()
    
    # Display available databases
    server_ids = display_available_databases()
    if not server_ids:
        return
    
    # Get user selection
    selected_server_id = get_user_selection(server_ids)
    if selected_server_id is None:
        print("👋 Goodbye!")
        return
    
    print(f"\n✅ Selected database for server: {selected_server_id}")
    print()
    
    # Connect to selected database
    try:
        db_client = get_server_db(selected_server_id)
        print(f"🔗 Connected to database successfully")
        print()
        
        # Show collection info
        collection_names = display_collection_info(db_client, selected_server_id)
        
        if not collection_names:
            return
            
        # Query the database
        query_database_top_results(db_client, selected_server_id)
        
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")


if __name__ == "__main__":
    try:
        run_interactive_query()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.exception("Full error details:")
