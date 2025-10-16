#!/usr/bin/env python3
"""
Test Summary Generation with multi-turn format
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


class TestSummary(unittest.TestCase):

    def setUp(self):
        # Patch Anthropic to avoid requiring real API
        self._anthropic_patcher = patch.object(ai_module, "Anthropic", MagicMock())
        self.mock_anthropic_class = self._anthropic_patcher.start()
        self.addCleanup(self._anthropic_patcher.stop)

    @patch.object(ai_module, "Anthropic")
    def test_generate_summary(self, mock_anthropic):
        """Test 1: Generate summary from multi-turn conversation"""
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "妈妈问天气，崽说天气不错。爸爸问工作情况，崽说在做新项目。爸爸提议周末视频。"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_key")

        mom_contact = get_mom_contacts().get("email") or "mom@example.com"
        dad_contact = get_dad_contacts().get("phone") or "dad@example.com"

        messages = [
            {"id": 1, "sender": mom_contact, "text": "崽，今天天气怎么样？", "is_from_me": False},
            {"id": 2, "sender": "Me", "text": "挺好的，阳光很好", "is_from_me": True},
            {"id": 3, "sender": dad_contact, "text": "工作忙不忙？", "is_from_me": False},
            {"id": 4, "sender": "Me", "text": "还好，最近在做一个新项目", "is_from_me": True},
            {"id": 5, "sender": dad_contact, "text": "周末要不要视频？", "is_from_me": False},
        ]

        summary = responder.generate_summary(messages)

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        print_api_call("TEST 1: Generate Summary (Multi-turn)", call_kwargs)

        print(f"Generated Summary: {summary}\n")
        self.assertEqual(summary, "妈妈问天气，崽说天气不错。爸爸问工作情况，崽说在做新项目。爸爸提议周末视频。")

    @patch.object(ai_module, "Anthropic")
    def test_generate_response_with_summary(self, mock_anthropic):
        """Test 2: Generate response using summary context"""
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "好啊！周末有空，几点视频？"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_key")

        dad_contact = get_dad_contacts().get("phone") or "dad@example.com"

        messages = [
            {"id": 5, "sender": dad_contact, "text": "周末要不要视频？", "is_from_me": False},
        ]

        summary = "妈妈问天气，崽说天气不错。爸爸问工作情况，崽说在做新项目。爸爸提议周末视频。"

        response = responder.generate_response_with_summary(messages, summary)

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        print_api_call("TEST 2: Response with Summary Context", call_kwargs)

        # Verify summary is in the user message content
        messages = call_kwargs.get("messages", [])
        last_user_msg = messages[-1]["content"] if messages else ""
        self.assertIn(summary, last_user_msg)
        self.assertIn("Conversation Summary", last_user_msg)

        print(f"Generated Response: {response}\n")
        self.assertEqual(response, "好啊！周末有空，几点视频？")

    @patch.object(ai_module, "Anthropic")
    def test_generate_startup_topic(self, mock_anthropic):
        """Test 3: Generate fresh startup topic with summary"""
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "妈咪，最近有没有发现什么好吃的餐厅？"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_key")

        summary = "妈妈问天气，崽说天气不错。爸爸问工作情况，崽说在做新项目。"

        topic = responder.generate_startup_topic(audience="family", summary=summary)

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        print_api_call("TEST 3: Fresh Startup Topic with Summary", call_kwargs)

        # Verify summary is in the user message content
        messages = call_kwargs.get("messages", [])
        user_msg = messages[0]["content"] if messages else ""
        self.assertIn(summary, user_msg)
        self.assertIn("conversation summary", user_msg.lower())

        print(f"Generated Topic: {topic}\n")
        self.assertEqual(topic, "妈咪，最近有没有发现什么好吃的餐厅？")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
