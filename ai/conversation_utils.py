#!/usr/bin/env python3
"""
Shared utilities for conversation formatting across responder, planner, and summarizer.
"""

from typing import List, Dict
from datetime import datetime


def parse_role_format_to_messages(text: str) -> List[Dict[str, str]]:
    """
    Parse conversation text with [role] labels into multi-turn API messages.

    Expected input format:
        [dad] message text
        [assistant] response text
        [mom] another message

    Returns:
        List of {"role": "user"/"assistant", "content": "text"} dicts
        - [assistant] → role: "assistant"
        - [mom]/[dad]/[other] → role: "user" (consecutive ones merged)
    """
    messages = []
    pending_user_messages = []
    assistant_roles = {"assistant", "me", "bot", "meg"}

    for line in text.strip().split('\n'):
        if not line.strip():
            continue

        # Parse [role] prefix
        if line.startswith('['):
            close_bracket = line.find(']')
            if close_bracket > 0:
                role = line[1:close_bracket].strip()
                content = line[close_bracket + 1:].strip()

                role_lower = role.lower()

                if role_lower in assistant_roles:
                    # Flush pending user messages first
                    if pending_user_messages:
                        messages.append({
                            "role": "user",
                            "content": "\n".join(pending_user_messages)
                        })
                        pending_user_messages = []

                    # Add assistant message
                    messages.append({
                        "role": "assistant",
                        "content": content
                    })
                else:
                    # Accumulate user message with role label
                    pending_user_messages.append(f"[{role}] {content}")
            else:
                # Malformed line, skip
                continue
        else:
            # Line without [role] prefix, skip
            continue

    # Flush remaining user messages
    if pending_user_messages:
        messages.append({
            "role": "user",
            "content": "\n".join(pending_user_messages)
        })

    return messages


def format_messages_to_role_string(messages: List[Dict[str, str]], bot_name: str = "Meg") -> str:
    """
    Format message dicts into [role] string format for simple text processing.

    Args:
        messages: List of message dicts with 'sender', 'text', 'is_from_me'
        bot_name: Name of the bot to identify bot messages

    Returns:
        String in format:
            [mom] message text
            [assistant] bot response
            [dad] another message
    """
    from config.contacts import get_mom_contacts, get_dad_contacts

    lines = []

    # Get contact info for relationship detection
    mom_contacts = {val for val in (
        (get_mom_contacts().get("email") or "").lower(),
        (get_mom_contacts().get("phone") or "").lower()
    ) if val}
    dad_contacts = {val for val in (
        (get_dad_contacts().get("email") or "").lower(),
        (get_dad_contacts().get("phone") or "").lower()
    ) if val}

    for msg in messages:
        # Determine if this is a bot message
        is_bot = msg.get('is_from_me') or (msg.get('sender') or "").lower() == bot_name.lower()

        if is_bot:
            role = "assistant"
        else:
            # Determine relationship
            sender_lower = (msg.get('sender') or "").lower()
            if sender_lower in mom_contacts:
                role = "mom"
            elif sender_lower in dad_contacts:
                role = "dad"
            else:
                role = "other"

        text = msg.get('text', '')

        # Format with role label
        if msg.get('is_reaction', False):
            lines.append(f"[{role}] {text}")
        else:
            lines.append(f"[{role}] {text}")

    return "\n".join(lines)


def get_time_context() -> str:
    """
    Get current time context for response generation.

    Returns:
        Time context string like "Today's date and time: Monday, January 15, 2025, afternoon"
    """
    now = datetime.now()
    hour = now.hour

    # Time of day
    if 6 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 18:
        time_of_day = "afternoon"
    elif 18 <= hour < 22:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    # Format: "Monday, January 15, 2025"
    date_str = now.strftime("%A, %B %d, %Y")

    return f"Today's date and time: {date_str}, {time_of_day}"
