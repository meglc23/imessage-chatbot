#!/usr/bin/env python3
"""
Test utilities - Shared helper functions for tests
"""

import json


def print_api_call(title, messages_sent, system_prompt=None, model=None, max_tokens=None):
    """
    Pretty print API call with full conversation history.

    Args:
        title: Test title/description
        messages_sent: List of message dicts with role and content
        system_prompt: Optional system prompt string
        model: Model name/identifier
        max_tokens: Maximum tokens for the API call
    """
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

    if model:
        print(f"\nModel: {model}")
    if max_tokens:
        print(f"Max Tokens: {max_tokens}")

    # Build full API call structure
    api_call = {}

    if system_prompt:
        api_call["system"] = system_prompt

    api_call["messages"] = messages_sent

    print("\n" + "-"*80)
    print("FULL JSON (Complete API Call):")
    print("-"*80)
    print(json.dumps(api_call, indent=2, ensure_ascii=False))
    print("="*80 + "\n")
