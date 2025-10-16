#!/usr/bin/env python3
"""
iMessage Chatbot - Main bot script that monitors and responds to messages
"""

import os
import time
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
from imessage_handler import iMessageHandler
from ai.responder import AIResponder
from ai.summarizer import ConversationSummarizer
import random
from config.contacts import get_mom_contacts, get_dad_contacts

def log_message(message, log_file="logs/bot_log.txt"):
    """Log messages to a file with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def main():
    # Load environment variables
    load_dotenv()

    # Configuration
    CHAT_NAME = os.getenv("CHAT_NAME")
    BOT_NAME = os.getenv("BOT_NAME", "AI Assistant")
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "20"))  # seconds

    if not CHAT_NAME:
        print("Error: CHAT_NAME not set in .env file")
        print("Please create a .env file with your configuration")
        return

    print(f"Starting iMessage Chatbot...")
    print(f"Chat: {CHAT_NAME}")
    print(f"Bot Name: {BOT_NAME}")
    print(f"AI Provider: {AI_PROVIDER}")
    print(f"Check Interval: {CHECK_INTERVAL} seconds")
    print(f"Logging to: logs/bot_log.txt")
    print("-" * 50)

    log_message(f"=== Bot Started ===")
    log_message(f"Chat: {CHAT_NAME}, Bot Name: {BOT_NAME}, AI Provider: {AI_PROVIDER}")

    # Load optional startup greeting configuration
    meg_handle = os.getenv("MEG_HANDLE")
    startup_greeting = os.getenv("STARTUP_GREETING", "Hi, I'm Meg! I'll be taking over the chat now.")

    # Variant startup greetings
    SELF_STARTUP_VARIANTS = ["我来了", "到啦～", "我在这儿", "到位！"]
    STARTUP_TOPIC_STARTERS = [
        "最近想去试试市中心那家新咖啡店，你们最近喝啥好喝的？",
        "周末我准备练个新菜谱，做味噌三文鱼，改天拍给你们看。",
        "这段时间在看一本摄影书，学了不少新构图的思路。",
        "我在找新的健身课，想着换换方式，你们最近运动得怎么样？",
        "我刚发现一个很有意思的纪录片，周末想追完，你们最近看啥？",
        "准备把阳台的小植物重新整理一下，你们那边花园怎么样？"
    ]

    # Note: Knowledge base and system prompts are now loaded automatically by AI modules

    # Initialize handlers
    try:
        imessage = iMessageHandler(CHAT_NAME, user_display_name=BOT_NAME)
        ai = AIResponder(provider=AI_PROVIDER)
        summarizer = ConversationSummarizer(provider=AI_PROVIDER)
    except Exception as e:
        print(f"Error initializing handlers: {e}")
        return

    print("Bot is running. Press Ctrl+C to stop.\n")

    # On startup: reply to the latest message in the chat
    print("Checking for latest message to reply to...")
    log_message("Startup: Checking for latest message")

    conversation_history: List[Dict[str, str]] = []
    fake_id_counter = 0
    def append_history(entry: Dict[str, str]) -> Dict[str, str]:
        nonlocal fake_id_counter, conversation_history
        entry_copy = dict(entry)
        entry_id = entry_copy.get('id')
        if isinstance(entry_id, (int, float)):
            fake_id_counter = max(fake_id_counter, entry_id)
        else:
            fake_id_counter = (fake_id_counter or 0) + 1
            entry_copy['id'] = fake_id_counter
        if not entry_copy.get('time'):
            entry_copy['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if entry_copy.get('is_from_me') or (entry_copy.get('sender') or "").lower() == BOT_NAME.lower():
            entry_copy['is_from_me'] = True
        conversation_history.append(entry_copy)
        if len(conversation_history) > 40:
            conversation_history = conversation_history[-40:]
        return entry_copy

    messages = imessage.get_recent_messages(count=30)
    log_message(f"Startup: Retrieved {len(messages)} messages for bootstrap")
    print(f"Bootstrap pulled {len(messages)} messages")

    # Generate summary of recent conversation
    conversation_summary = None
    if messages:
        print("\n📋 Generating conversation summary...")
        log_message("Startup: Generating conversation summary")
        conversation_summary = summarizer.generate_summary(messages)
        if conversation_summary:
            print(f"\n{'='*60}")
            print("📝 Recent Conversation Summary:")
            print(f"{'='*60}")
            print(conversation_summary)
            print(f"{'='*60}\n")
            log_message(f"Startup: Summary generated -> {conversation_summary}")
        else:
            print("⚠️  Could not generate summary\n")
            log_message("Startup: Failed to generate summary")

    for msg in messages:
        appended = append_history(msg)
        log_message(f"Startup: History appended -> {appended.get('sender')}: {appended.get('text')}")

    def respond_to_pending(context_label: str = "Startup", use_summary: bool = False) -> bool:
        nonlocal conversation_history, conversation_summary
        if not conversation_history:
            return False

        pending = []
        for msg in conversation_history:
            if msg.get('is_from_me') or (msg.get('sender') or "").lower() == BOT_NAME.lower():
                pending = []
            else:
                pending.append(msg)

        if not pending:
            return False

        log_message(f"{context_label}: Found {len(pending)} pending parent message(s) (replying in one message)")
        for order, pending_msg in enumerate(pending, start=1):
            sender = pending_msg.get('sender', 'Unknown')
            text = pending_msg.get('text', '')
            log_message(f"{context_label}: Pending #{order} → from {sender}: {text}")
            print(f"→ Catch-up ({context_label}) #{order} replying to {sender}: {text}")

        # Smart catch-up strategy
        total_messages = len(conversation_history)

        # Strategy: Use summary only for long conversations (>20 messages) when available
        if total_messages > 20 and use_summary and conversation_summary:
            log_message(f"{context_label}: Using summary for long conversation ({total_messages} messages)")
            print(f"  → Using summary (conversation has {total_messages} messages)")
            response = ai.generate_response_with_summary(conversation_history, conversation_summary)
        else:
            # Use full history for short conversations or when summary not available
            log_message(f"{context_label}: Using full history ({total_messages} messages)")
            print(f"  → Using full history ({total_messages} messages)")
            response = ai.generate_response(conversation_history)

        if not response:
            log_message(f"{context_label}: AI chose not to respond to pending batch")
            print("  → AI skipped pending batch")
            return False

        if imessage.send_message(response):
            log_message(f"{context_label}: Reply sent covering pending messages: {response}")
            print(f"  → Sent catch-up reply covering {len(pending)} messages: {response}")
            append_history({
                'sender': BOT_NAME,
                'text': response,
                'is_from_me': True
            })
            ai.last_reply = response
            return True

        log_message(f"{context_label}: ERROR sending batch reply")
        print("  → ERROR sending catch-up batch reply")
        return False

    if conversation_history:
        latest = conversation_history[-1]
        print(f"Latest message from {latest['sender']}: {latest['text'][:50]}...")
        log_message(f"Latest message: {latest['sender']}: {latest['text'][:80]}")

        # Try to respond to pending messages using summary context
        responded = respond_to_pending("Startup", use_summary=True)

        if not responded:
            sender_id = (latest.get('sender') or "").lower()
            print("→ All pending messages handled, considering fresh topic\n")
            log_message("→ Startup: no pending parent messages; considering new topic")

            # If the most recent message came from Meg herself → send only a short "I'm here" variant
            if meg_handle and latest.get('is_from_me'):
                variant = random.choice(SELF_STARTUP_VARIANTS)
                topic_intro = ai.generate_startup_topic("self", conversation_summary) or random.choice(STARTUP_TOPIC_STARTERS)
                message = f"{variant} {topic_intro}"
                print("→ Greeting (self detected)")
                log_message(f"→ Sending self-startup greeting: {message}")
                if imessage.send_message(message):
                    print("✓ Startup greeting (self) sent\n")
                    log_message("✓ Startup greeting (self) sent successfully")
                    append_history({
                        'sender': BOT_NAME,
                        'text': message,
                        'is_from_me': True
                    })
                    ai.last_reply = message
                else:
                    print("✗ Failed to send startup greeting (self)\n")
                    log_message("✗ Failed to send startup greeting (self)")

            else:
                topic_intro = ai.generate_startup_topic("family", conversation_summary) or random.choice(STARTUP_TOPIC_STARTERS)
                print("→ Starting a fresh topic")
                log_message(f"→ Sending fresh startup topic: {topic_intro}")
                success = imessage.send_message(topic_intro)
                if success:
                    print("✓ Fresh topic sent successfully\n")
                    log_message("✓ Fresh topic sent successfully")
                    append_history({
                        'sender': BOT_NAME,
                        'text': topic_intro,
                        'is_from_me': True
                    })
                    ai.last_reply = topic_intro
                else:
                    print("✗ Failed to send fresh topic message\n")
                    log_message("✗ Failed to send fresh topic message")
    else:
        print("→ No messages found in chat\n")
        log_message("→ No messages found for startup reply")

    print("-" * 50)
    print("Now monitoring for new messages...\n")

    # Initialize message tracking position after startup reply
    # This ensures get_new_messages() starts tracking from the current position
    _ = imessage.get_new_messages()  # Initialize last_message_id

    # Main loop
    try:
        while True:
            # Get new messages
            new_messages = imessage.get_new_messages()

            if new_messages:
                log_message(f"DETECTED {len(new_messages)} new message(s)")
                print(f"\n{len(new_messages)} new message(s):")
                for msg in new_messages:
                    sender_label = msg['sender']
                    if msg.get('is_from_me'):
                        sender_label = BOT_NAME
                    msg_log = f"  {sender_label}: {msg['text']}"
                    print(msg_log)
                    log_message(msg_log)
                    append_history(msg)

                # Check if we should respond to the latest message
                latest_message = conversation_history[-1] if conversation_history else new_messages[-1]

                # Don't respond to bot's own messages
                if latest_message.get('is_from_me') or latest_message['sender'] == BOT_NAME:
                    print("  → Skipping (own message)")
                    log_message("  → Skipping (own message)")
                else:
                    # Generate response
                    print("  → Thinking...")
                    log_message("  → Generating AI response...")
                    response = ai.generate_response(conversation_history)

                    if response:
                        print(f"  → Responding: {response}")
                        log_message(f"  → AI Response: {response}")
                        success = imessage.send_message(response)
                        if not success:
                            print("  → Failed to send message")
                            log_message("  → ERROR: Failed to send message")
                        else:
                            log_message("  → Message sent successfully")
                            append_history({
                                'sender': BOT_NAME,
                                'text': response,
                                'is_from_me': True
                            })
                            ai.last_reply = response
                    else:
                        print("  → AI decided not to respond")
                        log_message("  → AI decided not to respond (returned SKIP)")

            # Wait before checking again
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
