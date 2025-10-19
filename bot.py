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
from config.contacts import get_mom_contacts, get_dad_contacts
from config.constants import (
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_MAX_HISTORY_SIZE,
    DEFAULT_CONTEXT_WINDOW,
    SUMMARY_THRESHOLD
)
from loggings import log_message

def main():
    # Load environment variables
    load_dotenv()

    # Configuration
    CHAT_NAME = os.getenv("CHAT_NAME")
    BOT_NAME = os.getenv("BOT_NAME", "AI Assistant")
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", str(DEFAULT_CHECK_INTERVAL)))
    MAX_HISTORY_SIZE = int(os.getenv("MAX_HISTORY_SIZE", str(DEFAULT_MAX_HISTORY_SIZE)))
    CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", str(DEFAULT_CONTEXT_WINDOW)))

    if not CHAT_NAME:
        print("Error: CHAT_NAME not set in .env file")
        print("Please create a .env file with your configuration")
        return

    print(f"Starting iMessage Chatbot...")
    print(f"Chat: {CHAT_NAME}")
    print(f"Bot Name: {BOT_NAME}")
    print(f"AI Provider: {AI_PROVIDER}")
    print(f"Check Interval: {CHECK_INTERVAL} seconds")
    print(f"Logging to: data/logs/bot_log.txt")
    print("-" * 50)

    log_message(f"=== Bot Started ===")
    log_message(f"Chat: {CHAT_NAME}, Bot Name: {BOT_NAME}, AI Provider: {AI_PROVIDER}")

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
        if len(conversation_history) > MAX_HISTORY_SIZE:
            conversation_history = conversation_history[-MAX_HISTORY_SIZE:]
        return entry_copy

    messages = imessage.get_recent_messages(count=MAX_HISTORY_SIZE)
    log_message(f"Startup: Retrieved {len(messages)} messages for bootstrap")
    print(f"Bootstrap pulled {len(messages)} messages")

    # Generate summary of recent conversation (only if enough messages)
    conversation_summary = None
    if len(messages) >= SUMMARY_THRESHOLD:
        print(f"\n📋 Generating conversation summary ({len(messages)} messages)...")
        log_message(f"Startup: Generating conversation summary ({len(messages)} messages)")
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
    else:
        print(f"→ Skipping summary generation ({len(messages)} messages < {SUMMARY_THRESHOLD} threshold)\n")
        log_message(f"Startup: Skipping summary ({len(messages)} < {SUMMARY_THRESHOLD})")

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

        # Smart catch-up strategy: use summary if available
        total_messages = len(conversation_history)

        if use_summary and conversation_summary:
            log_message(f"{context_label}: Using summary-enhanced response ({total_messages} messages)")
            print(f"  → Using summary-enhanced response ({total_messages} messages)")
            response = ai.generate_response_with_summary(conversation_history, conversation_summary)
        else:
            # Use standard response without summary
            log_message(f"{context_label}: Using standard response ({total_messages} messages)")
            print(f"  → Using standard response ({total_messages} messages)")
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
            print("→ All pending messages handled, considering fresh topic\n")
            log_message("→ Startup: no pending parent messages; considering new topic")

            # Generate AI topic starter using recent messages
            recent_for_topic = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
            topic_intro = ai.generate_startup_topic(
                recent_messages=recent_for_topic,
                summary=conversation_summary
            )

            if not topic_intro:
                print("✗ Failed to generate startup topic, skipping\n")
                log_message("✗ Failed to generate startup topic")
            else:
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
