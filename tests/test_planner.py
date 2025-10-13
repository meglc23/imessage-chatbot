#!/usr/bin/env python3
"""
Test the AI planner with real message data from iMessage database
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ai.planner import plan_response, should_respond_with_plan
from scripts.parse_thread import extract_messages_for_tests, build_test_scenarios
from dotenv import load_dotenv

load_dotenv()


class TestPlanner:
    """Test suite for AI planner"""

    def __init__(self):
        self.test_results = []

    def test_real_messages(self, count: int = 50, max_scenarios: int = 10):
        """
        Test planner with real messages from iMessage database.

        Args:
            count: Number of messages to extract from database
            max_scenarios: Maximum number of test scenarios to run
        """
        print("\n" + "="*80)
        print("Testing AI Planner with Real Message Data")
        print("="*80)

        # Extract messages
        print("\n1. Extracting messages from iMessage database...")
        messages = extract_messages_for_tests(count=count)

        if not messages:
            print("✗ Failed to extract messages. Check database permissions.")
            return False

        print(f"✓ Extracted {len(messages)} messages")

        # Build test scenarios
        print("\n2. Building test scenarios...")
        scenarios = build_test_scenarios(messages)

        if not scenarios:
            print("✗ No valid test scenarios created")
            return False

        print(f"✓ Created {len(scenarios)} test scenarios")

        # Run tests on each scenario
        print(f"\n3. Testing planner on {min(len(scenarios), max_scenarios)} scenarios...")
        print("-"*80)

        for idx, scenario in enumerate(scenarios[:max_scenarios], 1):
            self._test_scenario(idx, scenario)

        # Print summary
        self._print_summary()

        return True

    def _test_scenario(self, idx: int, scenario: dict):
        """Test a single scenario"""
        print(f"\nScenario {idx}:")
        print(f"  Timestamp: {scenario['timestamp']}")
        print(f"  Sender: {scenario['sender']}")
        print(f"  Message: {scenario['new_message']}")
        print(f"  History (last 3 lines):")
        history_lines = scenario['history'].split('\n')
        for line in history_lines[-3:]:
            print(f"    {line}")

        # Determine sender relationship
        sender_info = "other"
        sender_lower = scenario['sender'].lower()
        if any(x in sender_lower for x in ['mom', '妈', 'mother']):
            sender_info = "mom"
        elif any(x in sender_lower for x in ['dad', '爸', 'father']):
            sender_info = "dad"

        # Get last bot reply from history (if any)
        last_bot_reply = None
        for line in reversed(history_lines):
            if line.startswith("Me:"):
                last_bot_reply = line[3:].strip()
                break

        # Call planner
        try:
            plan = plan_response(
                history=scenario['history'],
                new_msg=scenario['new_message'],
                sender_info=sender_info,
                last_bot_reply=last_bot_reply
            )

            # Check if should respond
            should_respond = should_respond_with_plan(plan)

            # Display results
            print(f"\n  Planner Output:")
            print(f"    Should Respond: {plan.get('should_respond')} (after filter: {should_respond})")
            print(f"    Intent: {plan.get('intent')}")
            print(f"    Tone: {plan.get('tone')}")
            print(f"    Response Length: {plan.get('response_length')}")
            print(f"    Topic: {plan.get('topic')}")
            print(f"    Hint: {plan.get('hint')}")

            # Validate plan structure
            is_valid = self._validate_plan(plan)

            # Store result
            self.test_results.append({
                'scenario_id': idx,
                'message': scenario['new_message'],
                'plan': plan,
                'should_respond': should_respond,
                'valid': is_valid,
                'sender_info': sender_info
            })

            if is_valid:
                print(f"  ✓ Plan structure valid")
            else:
                print(f"  ✗ Plan structure invalid")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            self.test_results.append({
                'scenario_id': idx,
                'message': scenario['new_message'],
                'error': str(e),
                'valid': False
            })

        print("-"*80)

    def _validate_plan(self, plan: dict) -> bool:
        """Validate that plan has correct structure and values"""
        required_fields = ['should_respond', 'intent', 'tone', 'response_length', 'topic', 'hint']

        # Check all fields present
        for field in required_fields:
            if field not in plan:
                print(f"    Missing field: {field}")
                return False

        # Validate field values
        valid_intents = ["ack", "ask_followup", "share_story", "reflect", "answer_question"]
        valid_tones = ["playful", "caring", "neutral", "enthusiastic"]
        valid_lengths = ["minimal", "short", "medium"]

        if plan['intent'] not in valid_intents:
            print(f"    Invalid intent: {plan['intent']}")
            return False

        if plan['tone'] not in valid_tones:
            print(f"    Invalid tone: {plan['tone']}")
            return False

        if plan['response_length'] not in valid_lengths:
            print(f"    Invalid response_length: {plan['response_length']}")
            return False

        if not isinstance(plan['should_respond'], bool):
            print(f"    should_respond is not boolean: {type(plan['should_respond'])}")
            return False

        return True

    def _print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("Test Summary")
        print("="*80)

        total = len(self.test_results)
        valid = sum(1 for r in self.test_results if r.get('valid', False))
        should_respond_count = sum(1 for r in self.test_results if r.get('should_respond', False))

        print(f"\nTotal scenarios tested: {total}")
        print(f"Valid plans: {valid}/{total}")
        print(f"Should respond: {should_respond_count}/{total}")

        # Intent distribution
        intents = {}
        for result in self.test_results:
            if 'plan' in result:
                intent = result['plan'].get('intent', 'unknown')
                intents[intent] = intents.get(intent, 0) + 1

        print(f"\nIntent Distribution:")
        for intent, count in sorted(intents.items()):
            print(f"  {intent}: {count}")

        # Tone distribution
        tones = {}
        for result in self.test_results:
            if 'plan' in result:
                tone = result['plan'].get('tone', 'unknown')
                tones[tone] = tones.get(tone, 0) + 1

        print(f"\nTone Distribution:")
        for tone, count in sorted(tones.items()):
            print(f"  {tone}: {count}")

        # Response length distribution
        lengths = {}
        for result in self.test_results:
            if 'plan' in result:
                length = result['plan'].get('response_length', 'unknown')
                lengths[length] = lengths.get(length, 0) + 1

        print(f"\nResponse Length Distribution:")
        for length, count in sorted(lengths.items()):
            print(f"  {length}: {count}")

        print("\n" + "="*80)

    def test_edge_cases(self):
        """Test planner with edge cases"""
        print("\n" + "="*80)
        print("Testing Edge Cases")
        print("="*80)

        test_cases = [
            {
                'name': 'Empty history',
                'history': '',
                'new_msg': '在吗？',
                'sender_info': 'mom'
            },
            {
                'name': 'Question with ?',
                'history': 'Me: 我在工作\n妈咪: 好的',
                'new_msg': '你那边天气怎么样？',
                'sender_info': 'mom'
            },
            {
                'name': 'Simple acknowledgment',
                'history': 'Me: 我今天很忙\n妈咪: 好的',
                'new_msg': '嗯嗯',
                'sender_info': 'mom'
            },
            {
                'name': 'Generic greeting',
                'history': 'Me: 早\n妈咪: 早',
                'new_msg': '早',
                'sender_info': 'dad'
            },
            {
                'name': 'Complex question',
                'history': 'Me: 我最近在做项目\n妈咪: 什么项目？',
                'new_msg': '你这个项目要做到什么时候啊？',
                'sender_info': 'mom'
            }
        ]

        for idx, case in enumerate(test_cases, 1):
            print(f"\nEdge Case {idx}: {case['name']}")
            print(f"  Message: {case['new_msg']}")

            try:
                plan = plan_response(
                    history=case['history'],
                    new_msg=case['new_msg'],
                    sender_info=case['sender_info']
                )

                should_respond = should_respond_with_plan(plan)

                print(f"  Should Respond: {plan.get('should_respond')} (after filter: {should_respond})")
                print(f"  Intent: {plan.get('intent')}")
                print(f"  Response Length: {plan.get('response_length')}")

                # Special assertions
                if '?' in case['new_msg'] or '吗' in case['new_msg']:
                    if plan.get('intent') == 'answer_question':
                        print(f"  ✓ Correctly identified as question")
                    else:
                        print(f"  ⚠ Expected answer_question intent for question")

                if case['new_msg'] in ['嗯嗯', '好', '哦']:
                    if not plan.get('should_respond'):
                        print(f"  ✓ Correctly decided not to respond to minimal ack")
                    else:
                        print(f"  ⚠ May want to skip response to minimal ack")

            except Exception as e:
                print(f"  ✗ Error: {e}")

            print("-"*80)


def main():
    """Main test runner"""
    tester = TestPlanner()

    # Test with real messages
    print("\n🧪 Running Planner Tests\n")

    success = tester.test_real_messages(count=50, max_scenarios=10)

    if not success:
        print("\n⚠️  Real message tests could not run (check database access)")
        print("Falling back to edge case tests only...\n")

    # Test edge cases
    tester.test_edge_cases()

    print("\n✓ All tests completed!")


if __name__ == "__main__":
    main()
