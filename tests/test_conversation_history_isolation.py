#!/usr/bin/env python3
"""
Test to verify that generate_response does not modify the original conversation_history.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.responder import AIResponder
import copy

def test_conversation_history_not_modified():
    """
    Verify that calling generate_response does not modify the original conversation_history.
    """
    # Create a simple conversation history
    original_history = [
        {'id': 1, 'sender': '+1234567890', 'text': '今天天气怎么样？', 'is_from_me': False},
        {'id': 2, 'sender': 'Meg', 'text': '挺好的', 'is_from_me': True},
        {'id': 3, 'sender': '+0987654321', 'text': '周末有什么计划吗？', 'is_from_me': False},
    ]

    # Make a deep copy to compare later
    history_before = copy.deepcopy(original_history)

    # Initialize AIResponder
    ai = AIResponder(provider="anthropic")

    # Call generate_response (it might fail due to API, but that's ok - we just want to check if history is modified)
    try:
        ai.generate_response(original_history, max_tokens=50)
    except Exception as e:
        print(f"Note: generate_response raised exception (expected): {e}")

    # Verify that original_history was not modified
    assert original_history == history_before, "conversation_history was modified!"

    # Verify each message dict was not modified
    for i, (orig, before) in enumerate(zip(original_history, history_before)):
        assert orig == before, f"Message {i} was modified!"
        assert orig is not before, f"Message {i} should be different objects (deep copy check)"

    print("✅ Test passed: conversation_history is not modified by generate_response")

if __name__ == "__main__":
    test_conversation_history_not_modified()
