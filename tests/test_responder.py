#!/usr/bin/env python3
"""
Test AIResponder with multi-turn format
Shows full API calls, system prompts, and messages
"""

import os
import sys
import json
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import ai.responder as ai_module
from ai.responder import AIResponder
from config.contacts import get_mom_contacts, get_dad_contacts


def print_api_call(title, call_kwargs):
    """Pretty print API call details"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

    print("\nModel:", call_kwargs.get("model"))
    print("Max Tokens:", call_kwargs.get("max_tokens"))

    print("\n" + "-"*80)
    print("SYSTEM PROMPT:")
    print("-"*80)
    system = call_kwargs.get("system", "")
    print(system)

    print("\n" + "-"*80)
    print("MESSAGES:")
    print("-"*80)
    messages = call_kwargs.get("messages", [])
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}:")
        print(f"  Role: {msg['role']}")
        print(f"  Content:")
        content = msg['content']
        for line in content.split('\n'):
            print(f"    {line}")

    print("\n" + "-"*80)
    print("FULL JSON (messages only):")
    print("-"*80)
    print(json.dumps(messages, indent=2, ensure_ascii=False))
    print("="*80 + "\n")


class TestAIResponder(unittest.TestCase):

    def setUp(self):
        # Patch Anthropic to avoid requiring real API
        self._anthropic_patcher = patch.object(ai_module, "Anthropic", MagicMock())
        self.mock_anthropic_class = self._anthropic_patcher.start()
        self.addCleanup(self._anthropic_patcher.stop)

    @patch.object(ai_module, "Anthropic")
    def test_simple_conversation(self, mock_anthropic):
        """Test 1: Simple single message"""
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "挺好的，最近在做新项目"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_key")

        mom_contact = get_mom_contacts().get("email") or "mom@example.com"
        messages = [
            {"id": 1, "sender": mom_contact, "text": "最近怎么样？", "is_from_me": False},
        ]

        reply = responder.generate_response(messages)

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        print_api_call("TEST 1: Simple Conversation (1 message)", call_kwargs)

        print(f"Generated Reply: {reply}\n")
        self.assertEqual(reply, "挺好的，最近在做新项目")

    @patch.object(ai_module, "Anthropic")
    def test_merged_user_messages(self, mock_anthropic):
        """
        Test 2: Mom and Dad both send messages between two bot replies
        Shows how consecutive user messages are merged
        """
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "周末打算休息一下，可能去hiking"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_key")

        mom_contact = get_mom_contacts().get("email") or "mom@example.com"
        dad_contact = get_dad_contacts().get("phone") or "dad@example.com"

        # Conversation: dad -> mom -> bot -> dad -> mom
        messages = [
            {"id": 1, "sender": dad_contact, "text": "崽，最近工作忙吗？", "is_from_me": False},
            {"id": 2, "sender": mom_contact, "text": "对啊，别太累了", "is_from_me": False},
            {"id": 3, "sender": "Meg", "text": "还好，项目进展不错", "is_from_me": True},
            {"id": 4, "sender": dad_contact, "text": "周末有什么计划吗？", "is_from_me": False},
            {"id": 5, "sender": mom_contact, "text": "要不要回来看看？", "is_from_me": False},
        ]

        reply = responder.generate_response(messages)

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        print_api_call("TEST 2: Mom & Dad Messages Merged Between Bot Replies", call_kwargs)

        # Verify structure
        api_messages = call_kwargs["messages"]

        print("Expected structure:")
        print("  1. user: [dad] + [mom] merged")
        print("  2. assistant: bot reply")
        print("  3. user: [dad] + [mom] + instructions\n")

        # First user message should have both [dad] and [mom]
        first_user = api_messages[0]
        self.assertEqual(first_user["role"], "user")
        self.assertIn("[dad]", first_user["content"])
        self.assertIn("[mom]", first_user["content"])

        # Second should be assistant
        self.assertEqual(api_messages[1]["role"], "assistant")

        # Third should be user with both [dad] and [mom]
        last_user = api_messages[2]
        self.assertEqual(last_user["role"], "user")
        self.assertIn("[dad]", last_user["content"])
        self.assertIn("[mom]", last_user["content"])

        print(f"Generated Reply: {reply}\n")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
