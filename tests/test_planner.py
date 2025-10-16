#!/usr/bin/env python3
"""
Test AI Planner with multi-turn format
Shows full API calls and prompts
"""

import sys
import os
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ai import planner as planner_module
from ai.planner import plan_response, should_respond_with_plan


def print_api_call(title, messages_sent):
    """Pretty print planner API call"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

    print("\nModel: claude-3-haiku-20240307 (Planner)")
    print("Max Tokens: 200")

    print("\n" + "-"*80)
    print("MESSAGES SENT TO PLANNER API:")
    print("-"*80)

    for i, msg in enumerate(messages_sent, 1):
        print(f"\nMessage {i}:")
        print(f"  Role: {msg['role']}")
        print(f"  Content:")
        content = msg['content']
        for line in content.split('\n'):
            print(f"    {line}")

    print("\n" + "-"*80)
    print("FULL JSON:")
    print("-"*80)
    print(json.dumps(messages_sent, indent=2, ensure_ascii=False))
    print("="*80 + "\n")


class TestPlanner(unittest.TestCase):

    def test_simple_question(self):
        """Test 1: Simple question planning"""
        captured_messages = []

        def mock_call_model(messages):
            nonlocal captured_messages
            captured_messages = messages
            return json.dumps({
                "should_respond": True,
                "intent": "answer_question",
                "tone": "caring",
                "response_length": "short",
                "topic": "family",
                "hint": "be warm"
            })

        with patch.object(planner_module, '_call_model', side_effect=mock_call_model):
            history = "[mom] 最近怎么样？"
            new_msg = "最近怎么样？"

            plan = plan_response(
                history=history,
                new_msg=new_msg,
                sender_info="mom"
            )

            print_api_call("TEST 1: Simple Question", captured_messages)

            print(f"Plan Result:")
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            print()

            self.assertTrue(plan.get('should_respond'))
            self.assertEqual(plan.get('intent'), 'answer_question')

    def test_multi_turn_conversation(self):
        """Test 2: Multi-turn conversation with bot history"""
        captured_messages = []

        def mock_call_model(messages):
            nonlocal captured_messages
            captured_messages = messages
            return json.dumps({
                "should_respond": True,
                "intent": "ask_followup",
                "tone": "playful",
                "response_length": "medium",
                "topic": "weekend",
                "hint": "be enthusiastic"
            })

        with patch.object(planner_module, '_call_model', side_effect=mock_call_model):
            # History with bot's previous reply
            history = """[dad] 崽，今天天气怎么样？
[me] 挺好的，天气不错
[mom] 记得多喝水哦
[me] 好的妈咪"""

            new_msg = "周末有什么计划吗？"

            plan = plan_response(
                history=history,
                new_msg=new_msg,
                sender_info="dad",
                last_bot_reply="好的妈咪"
            )

            print_api_call("TEST 2: Multi-turn with Bot History", captured_messages)

            print(f"Plan Result:")
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            print()

            # Verify multi-turn structure
            # Should have: [user: dad] -> [assistant: me] -> [user: mom] -> [assistant: me] -> [user: planning instructions]
            self.assertTrue(len(captured_messages) >= 4)

            # Check alternating pattern
            self.assertEqual(captured_messages[0]['role'], 'user')
            self.assertIn('[dad]', captured_messages[0]['content'])

            self.assertEqual(captured_messages[1]['role'], 'assistant')
            self.assertIn('挺好的，天气不错', captured_messages[1]['content'])

            self.assertEqual(captured_messages[2]['role'], 'user')
            self.assertIn('[mom]', captured_messages[2]['content'])

            self.assertEqual(captured_messages[3]['role'], 'assistant')
            self.assertIn('好的妈咪', captured_messages[3]['content'])

            print("✓ Verified multi-turn alternating pattern")
            print("✓ Bot replies ([me]) correctly converted to assistant role\n")

    def test_merged_user_messages(self):
        """Test 3: Mom and Dad both send messages between bot replies"""
        captured_messages = []

        def mock_call_model(messages):
            nonlocal captured_messages
            captured_messages = messages
            return json.dumps({
                "should_respond": True,
                "intent": "reflect",
                "tone": "caring",
                "response_length": "medium",
                "topic": "plans",
                "hint": "be thoughtful"
            })

        with patch.object(planner_module, '_call_model', side_effect=mock_call_model):
            # Dad and mom both send messages between bot replies
            history = """[dad] 崽，最近工作忙吗？
[mom] 对啊，别太累了
[me] 还好，项目进展不错
[dad] 周末有什么计划吗？
[mom] 要不要回来看看？"""

            new_msg = "周末有什么计划吗？"

            plan = plan_response(
                history=history,
                new_msg=new_msg,
                sender_info="dad",
                last_bot_reply="还好，项目进展不错"
            )

            print_api_call("TEST 3: Mom & Dad Messages Merged", captured_messages)

            print(f"Plan Result:")
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            print()

            # Verify: First message should have both [dad] and [mom] merged
            first_user = captured_messages[0]
            self.assertEqual(first_user['role'], 'user')
            self.assertIn('[dad]', first_user['content'])
            self.assertIn('[mom]', first_user['content'])

            print("✓ Verified [dad] and [mom] messages are merged in first user message")
            print("✓ Multi-turn structure preserved\n")

    def test_should_respond_logic(self):
        """Test 4: Should respond decision logic"""
        print("\n" + "="*80)
        print("  TEST 4: Should Respond Logic")
        print("="*80 + "\n")

        # Test 1: Should respond to question
        plan1 = {
            "should_respond": True,
            "intent": "answer_question",
            "response_length": "short"
        }
        result1 = should_respond_with_plan(plan1)
        print(f"Question (should_respond=True, intent=answer_question)")
        print(f"  → Should respond: {result1}")
        self.assertTrue(result1)

        # Test 2: Should skip minimal ack (50% chance, but we can test the logic)
        plan2 = {
            "should_respond": True,
            "intent": "ack",
            "response_length": "minimal"
        }
        print(f"\nMinimal ack (should_respond=True, intent=ack, length=minimal)")
        print(f"  → Has 50% random filter (may skip)")

        # Test 3: Should not respond if plan says no
        plan3 = {
            "should_respond": False,
            "intent": "ack",
            "response_length": "short"
        }
        result3 = should_respond_with_plan(plan3)
        print(f"\nPlan says no (should_respond=False)")
        print(f"  → Should respond: {result3}")
        self.assertFalse(result3)

        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
