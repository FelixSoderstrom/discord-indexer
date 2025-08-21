#!/usr/bin/env python3
"""ChromaDB connection test script.

Tests the database setup by adding mock data, querying it, and cleaning up.
ChromaDB automatically handles embedding generation from text.
"""

import sys
import os
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db import initialize_db, get_db


def main():
    """Main test function."""
    print("🧪 ChromaDB Connection Test")
    print("=" * 40)

    # Initialize database
    print("🗄️ Initializing database...")
    try:
        initialize_db()
        client = get_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return

    # Create test collection
    collection_name = "test_messages"
    print(f"📁 Creating collection: {collection_name}")

    try:
        # Delete collection if it exists (for clean testing)
        try:
            client.delete_collection(collection_name)
            print("🗑️ Deleted existing test collection")
        except:
            pass  # Collection didn't exist, that's fine

        collection = client.create_collection(collection_name)
        print("✅ Collection created successfully")
    except Exception as e:
        print(f"❌ Collection creation failed: {e}")
        return

    # Mock data with metadata
    mock_messages = [
        "Hey everyone, how's the weather today?",
        "I just finished a great book about machine learning",
        "Anyone want to grab coffee this afternoon?",
        "The new update looks amazing, great work team!",
        "I'm having trouble with my Python code, can someone help?",
        "Just deployed the new feature to production",
        "Looking forward to the weekend plans",
        "Does anyone know a good restaurant nearby?",
        "The meeting has been moved to 3 PM tomorrow",
        "Happy birthday! Hope you have a wonderful day",
    ]

    senders = [
        "Alice",
        "Bob",
        "Charlie",
        "Diana",
        "Eve",
        "Frank",
        "Grace",
        "Henry",
        "Iris",
        "Jack",
    ]

    # Prepare data for insertion
    documents = mock_messages
    metadatas = [
        {"sender": sender, "type": "test_message"} for sender in senders
    ]
    ids = [f"test_msg_{i}" for i in range(len(mock_messages))]

    # Add mock data
    print("📤 Adding mock data...")
    try:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ Added {len(mock_messages)} mock messages")
    except Exception as e:
        print(f"❌ Failed to add mock data: {e}")
        return

    # Query loop
    print("\n🔍 Query Testing")
    print("Enter search queries (empty line to quit):")

    while True:
        query = input("\nQuery: ").strip()
        if not query:
            break

        try:
            results = collection.query(
                query_texts=[query],
                n_results=3,  # Get top 3 results
            )

            print(f"\n📊 Results for '{query}':")
            print("-" * 30)

            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(
                    zip(
                        results["documents"][0],
                        results["metadatas"][0],
                        results["distances"][0],
                    )
                ):
                    print(f"{i+1}. Sender: {metadata['sender']}")
                    print(f"   Message: {doc}")
                    print(f"   Distance: {distance:.4f}")
                    print()
            else:
                print("No results found")

        except Exception as e:
            print(f"❌ Query failed: {e}")

    # Cleanup
    print("\n🧹 Cleaning up...")
    try:
        client.delete_collection(collection_name)
        print("✅ Test collection deleted")
        print("🎉 Test completed successfully!")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")


if __name__ == "__main__":
    main()
