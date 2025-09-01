#!/usr/bin/env python3

import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from llm.agents.dm_assistant import DMAssistant


async def test_dm_chat():
    # Mock message
    mock_message = "Hello! How are you doing today?"
    mock_user_id = "test_user_123"
    mock_user_name = "TestUser"
    
    # Instantiate agent (should auto-download model)
    assistant = DMAssistant()
    
    # Perform single chat completion
    response = await assistant.respond_to_dm(mock_message, mock_user_id, mock_user_name)
    
    print(f"User: {mock_message}")
    print(f"Assistant: {response}")


if __name__ == "__main__":
    asyncio.run(test_dm_chat())
