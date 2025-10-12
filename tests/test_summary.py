#!/usr/bin/env python3
"""
Test script for conversation summary generation
"""

import sys
import os
# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.responder import AIResponder
from config.contacts import get_mom_contacts, get_dad_contacts

# Get contact info from contacts.py
mom_contact = get_mom_contacts().get("email") or get_mom_contacts().get("phone") or "mom@example.com"
dad_contact = get_dad_contacts().get("phone") or get_dad_contacts().get("email") or "+1234567890"

# Sample test messages
test_messages = [
    {
        'id': 1,
        'sender': mom_contact,
        'text': '崽，今天天气怎么样？',
        'time': '2025-01-10 10:00:00',
        'is_from_me': False,
        'is_reaction': False
    },
    {
        'id': 2,
        'sender': 'Me',
        'text': '挺好的，阳光很好',
        'time': '2025-01-10 10:05:00',
        'is_from_me': True,
        'is_reaction': False
    },
    {
        'id': 3,
        'sender': mom_contact,
        'text': None,
        'time': '2025-01-10 10:06:00',
        'is_from_me': False,
        'is_reaction': True
    },
    {
        'id': 4,
        'sender': dad_contact,
        'text': '工作忙不忙？',
        'time': '2025-01-10 14:00:00',
        'is_from_me': False,
        'is_reaction': False
    },
    {
        'id': 5,
        'sender': 'Me',
        'text': '还好，最近在做一个新项目',
        'time': '2025-01-10 14:10:00',
        'is_from_me': True,
        'is_reaction': False
    },
    {
        'id': 6,
        'sender': dad_contact,
        'text': '周末要不要视频？',
        'time': '2025-01-10 15:00:00',
        'is_from_me': False,
        'is_reaction': False
    }
]

if __name__ == "__main__":
    print("Testing conversation summary and summary-aware responses...\n")

    try:
        ai = AIResponder(provider="anthropic")

        print("Sample messages:")
        print("-" * 60)
        for msg in test_messages:
            sender = ai.alias_sender(msg['sender'])
            if msg.get('is_reaction'):
                print(f"{sender} [Reacted ❤️]")
            else:
                print(f"{sender}: {msg['text']}")
        print("-" * 60)

        # Test 1: Generate summary
        print("\n🧪 Test 1: Generating summary...\n")
        summary = ai.generate_summary(test_messages)

        if summary:
            print("=" * 60)
            print("📝 Summary:")
            print("=" * 60)
            print(summary)
            print("=" * 60)
        else:
            print("❌ Failed to generate summary")
            exit(1)

        # Test 2: Generate summary-aware response (should answer the pending question)
        print("\n🧪 Test 2: Generating summary-aware response...\n")
        print("Expected: Should respond to the pending question '周末要不要视频？'\n")

        summary_response = ai.generate_response_with_summary(test_messages, summary)

        if summary_response:
            print("✅ Summary-aware response:")
            print(f"   → {summary_response}")
        else:
            print("⚠️  No pending questions detected (returned None)")

        # Test 3: Generate fresh topic using summary context
        print("\n🧪 Test 3: Generating fresh topic with summary context...\n")
        print("Expected: Should start a NEW topic different from recent discussions\n")

        fresh_topic = ai.generate_startup_topic("family", summary)

        if fresh_topic:
            print("✅ Fresh topic:")
            print(f"   → {fresh_topic}")
        else:
            print("❌ Failed to generate fresh topic")

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure ANTHROPIC_API_KEY is set in your environment")
