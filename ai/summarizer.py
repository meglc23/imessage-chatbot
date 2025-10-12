#!/usr/bin/env python3
"""
Conversation Summarizer - Generates summaries of conversation history
"""

import os
from typing import List, Dict, Optional
from anthropic import Anthropic
from datetime import datetime

from prompts.system_prompts import SUMMARY_GENERATION_PROMPT_TEMPLATE


def _debug_log(message: str, log_file: str = "logs/bot_log.txt"):
    """Append debug information to the shared bot log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}]   DEBUG: {message}\n")
    except Exception:
        pass


class ConversationSummarizer:
    def __init__(self, provider: str = "anthropic", api_key: Optional[str] = None):
        """
        Initialize the conversation summarizer.

        Args:
            provider: "anthropic" or "openai"
            api_key: API key for the provider (uses env var if not provided)
        """
        self.provider = provider.lower()

        if self.provider == "anthropic":
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment")
            self.client = Anthropic(api_key=self.api_key)
            self.model = "claude-3-haiku-20240307"

        elif self.provider == "openai":
            try:
                import openai
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")

            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            self.client = openai.OpenAI(api_key=self.api_key)
            self.model = "gpt-4"

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def alias_sender(self, sender: str) -> str:
        """Map raw sender identifiers to display names."""
        try:
            from config.contacts import CONTACT_ALIASES
            if not sender:
                return sender
            key = sender.strip().lower()

            # User aliases
            if key in {"meg", "me", "chen"}:
                return "我"

            # Contact aliases
            if key in CONTACT_ALIASES:
                return CONTACT_ALIASES[key]

            return sender
        except ImportError:
            return sender

    def generate_summary(self, messages: List[Dict[str, str]], max_tokens: int = 300) -> Optional[str]:
        """
        Generate a summary of recent conversation history.

        Args:
            messages: List of message dictionaries to summarize
            max_tokens: Maximum tokens for the summary

        Returns:
            A concise summary of the conversation, or None on failure
        """
        if not messages:
            return None

        # Format messages for summary
        formatted_messages = []
        for msg in messages:
            sender_alias = self.alias_sender(msg['sender'])
            text = msg.get('text', '')
            if msg.get('is_reaction', False):
                formatted_messages.append(f"{sender_alias} {text}")
            else:
                formatted_messages.append(f"{sender_alias}: {text}")

        conversation_text = "\n".join(formatted_messages)

        summary_prompt = SUMMARY_GENERATION_PROMPT_TEMPLATE.format(
            conversation_text=conversation_text
        )

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system="You are a helpful assistant that summarizes conversations accurately and concisely.",
                    messages=[{
                        "role": "user",
                        "content": summary_prompt
                    }]
                )
                summary = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes conversations accurately and concisely."},
                        {"role": "user", "content": summary_prompt}
                    ]
                )
                summary = response.choices[0].message.content.strip()
            else:
                return None

            _debug_log(f"Generated conversation summary: {summary}")
            return summary or None
        except Exception as e:
            print(f"✗ Error generating summary: {e}")
            return None
