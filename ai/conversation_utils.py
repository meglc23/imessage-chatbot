#!/usr/bin/env python3
"""
Shared utilities for conversation formatting across responder, planner, and summarizer.
"""

from typing import List, Dict


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

    for line in text.strip().split('\n'):
        if not line.strip():
            continue

        # Parse [role] prefix
        if line.startswith('['):
            close_bracket = line.find(']')
            if close_bracket > 0:
                role = line[1:close_bracket].strip()
                content = line[close_bracket + 1:].strip()

                if role == 'assistant':
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
