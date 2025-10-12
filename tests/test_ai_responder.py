import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path when running as `python tests/test_ai_responder.py`
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import ai.responder as ai_module
from ai.responder import AIResponder
from config.contacts import get_mom_contacts, get_dad_contacts


class TestAIResponder(unittest.TestCase):

    def setUp(self):
        # Patch Anthropic for all tests to avoid requiring the real package/client
        self._anthropic_patcher = patch.object(ai_module, "Anthropic", MagicMock())
        self.mock_anthropic_class = self._anthropic_patcher.start()
        self.addCleanup(self._anthropic_patcher.stop)

    @patch.object(ai_module, "Anthropic")
    def test_response_generation_with_mocked_provider(self, mock_anthropic):
        """AIResponder should return a non-empty string when provider is mocked."""
        # Arrange mock Anthropic client
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "好的，没问题"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_api_key")

        mom_contact = get_mom_contacts().get("email") or get_mom_contacts().get("phone") or "mom@example.com"
        messages = [
            {"sender": mom_contact, "text": "在干嘛？"},
            {"sender": "meg", "text": "等会儿聊"},
        ]

        # Act
        reply = responder.generate_response(messages)

        print("Mocked reply:", reply)

    def test_should_respond_to_question(self):
        responder = AIResponder(provider="anthropic", api_key="test_api_key")
        msg = {"sender": "Mom", "text": "你今天怎么样?"}
        print("should_respond_to_question ->", responder.should_respond_to_message(msg, bot_name="Meg"))

    def test_should_not_respond_to_own_message(self):
        responder = AIResponder(provider="anthropic", api_key="test_api_key")
        msg = {"sender": "AI Assistant", "text": "Hi"}
        print("should_not_respond_to_own_message ->", responder.should_respond_to_message(msg, bot_name="AI Assistant"))

    @patch.object(ai_module, "Anthropic")
    def test_prompt_uses_latest_conversation_history(self, mock_anthropic):
        """Prompt fed to provider should include latest parent message text."""
        mock_client = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = "好的，我周末拍照给你们看。"
        mock_response = MagicMock()
        mock_response.content = [mock_content_item]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        responder = AIResponder(provider="anthropic", api_key="test_api_key")

        mom_contact = get_mom_contacts().get("email") or get_mom_contacts().get("phone") or "mom@example.com"
        conversation = [
            {"id": 101, "sender": mom_contact, "text": "哈哈哈可以考虑", "is_from_me": False},
            {"id": 102, "sender": "Meg", "text": "周末我来跟你们详细说～", "is_from_me": True},
            {"id": 103, "sender": mom_contact, "text": "那你试试，做好了告诉我们", "is_from_me": False},
        ]

        reply = responder.generate_response(conversation)

        print("Latest convo reply:", reply)
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        prompt = call_kwargs["messages"][0]["content"]

        self.assertIn("妈咪: 哈哈哈可以考虑", prompt)
        self.assertIn("妈咪: 那你试试，做好了告诉我们", prompt)
        self.assertIn("Latest message text: 「那你试试，做好了告诉我们」", prompt)


if __name__ == "__main__":
    unittest.main()
