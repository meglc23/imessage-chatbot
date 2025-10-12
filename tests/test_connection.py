#!/usr/bin/env python3
"""
Test Connection - Quick test script to verify iMessage bot setup
"""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv()
CHAT_NAME = os.getenv("CHAT_NAME", "Home")

print("=" * 70)
print("iMessage Chatbot Connection Test")
print("=" * 70)

# Test 1: Check environment
print("\n1. Checking environment configuration...")
print(f"   Chat Name: {CHAT_NAME}")
api_key = os.getenv("ANTHROPIC_API_KEY")
if api_key:
    print(f"   API Key: sk-***...{api_key[-4:]} ✓")
else:
    print("   API Key: NOT FOUND ✗")

# Test 2: Test iMessage Handler
print("\n2. Testing iMessage connection...")
try:
    from imessage_handler import iMessageHandler
    handler = iMessageHandler(CHAT_NAME)
    print(f"   ✓ Handler initialized")

    print(f"   Attempting to read messages from '{CHAT_NAME}'...")
    messages = handler.get_recent_messages(5)

    if messages:
        print(f"   ✓ SUCCESS! Retrieved {len(messages)} messages:")
        print()
        for i, msg in enumerate(messages, 1):
            text = msg['text'][:70] + '...' if len(msg['text']) > 70 else msg['text']
            print(f"      {i}. {msg['sender']}: {text}")
        print()
        print("   ✅ iMessage connection working!")
    else:
        print("   ✗ No messages retrieved")
        print("   This usually means:")
        print("      - Chat name is incorrect")
        print("      - Terminal needs Full Disk Access permission")

except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 3: Test AI Responder
print("\n3. Testing AI connection...")
try:
    from ai.responder import AIResponder
    ai = AIResponder(provider="anthropic")
    print("   ✓ AI initialized")

    print("   Testing AI response generation...")
    test_messages = [
        {"sender": "Test User", "text": "Hello! Can you hear me?"}
    ]

    response = ai.generate_response(test_messages)
    if response:
        print(f"   ✓ AI Response: {response}")
        print("   ✅ AI connection working!")
    else:
        print("   ○ AI decided not to respond (this is normal)")
        print("   ✅ AI connection working!")

except Exception as e:
    print(f"   ✗ Error: {e}")
    if "API_KEY" in str(e):
        print("   Make sure your API key is set in .env file")

# Test 4: Test message sending (optional)
print("\n4. Test sending a message (optional)")
print("   WARNING: This will send a real message to your chat!")
response = input("   Send test message? (yes/no): ").lower().strip()

if response == "yes":
    try:
        from imessage_handler import iMessageHandler
        handler = iMessageHandler(CHAT_NAME)
        test_msg = "🤖 Test message - Bot is connected!"
        print(f"   Sending: {test_msg}")
        success = handler.send_message(test_msg)
        if success:
            print("   ✓ Message sent successfully!")
            print("   ✅ Everything is working! Run: python bot.py")
        else:
            print("   ✗ Failed to send message")
    except Exception as e:
        print(f"   ✗ Error: {e}")
else:
    print("   Skipped")

print("\n" + "=" * 70)
print("Test Complete")
print("=" * 70)

# Summary
print("\nNext steps:")
print("  • If all tests passed: run 'python bot.py'")
print("  • If message reading failed: Grant Full Disk Access to Terminal")
print("  • If API failed: Check your API key in .env file")
