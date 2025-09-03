#!/usr/bin/env python3
"""Simple ChromaDB query test tool.

Scans available databases, lets user select one, and query for top 3 matches.
"""

from pathlib import Path
from typing import List, Optional
from src.db.setup_db import get_db


def scan_databases() -> List[int]:
    """Scan src/db/databases/ for numerical server IDs."""
    db_path = Path("src/db/databases")
    
    if not db_path.exists():
        print("No database directory found")
        return []
    
    server_ids = []
    for item in db_path.iterdir():
        if item.is_dir() and item.name.isdigit():
            server_ids.append(int(item.name))
    
    return sorted(server_ids)


def select_database(server_ids: List[int]) -> Optional[int]:
    """Ask user which database to use."""
    if not server_ids:
        print("No databases found")
        return None
    
    print("Available databases:")
    for i, server_id in enumerate(server_ids, 1):
        print(f"{i}. {server_id}")
    
    while True:
        try:
            choice = input(f"Select database (1-{len(server_ids)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(server_ids):
                return server_ids[choice_num - 1]
            else:
                print(f"Enter number between 1 and {len(server_ids)}")
        except (ValueError, KeyboardInterrupt):
            return None


def query_database(server_id: int) -> None:
    """Query database and show top 3 matches."""
    try:
        db_client = get_db(server_id)
        collections = db_client.list_collections()
        
        if not collections:
            print("No collections found in database")
            return
        
        # Use first collection (assuming there's only one)
        collection = collections[0]
        print(f"Using collection: {collection.name}")
        
        query = input("Enter query: ").strip()
        if not query:
            return
        
        results = collection.query(query_texts=[query], n_results=3)
        
        if not results['documents'] or not results['documents'][0]:
            print("No results found")
            return
        
        print(f"\nTop 3 matches:")
        for i, doc in enumerate(results['documents'][0], 1):
            print(f"{i}. {doc}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main function."""
    server_ids = scan_databases()
    selected_id = select_database(server_ids)
    
    if selected_id:
        query_database(selected_id)


if __name__ == "__main__":
    main()
