#!/usr/bin/env python3
"""
Conversation Summarizer - Generates summaries of conversation history
"""

import os
from typing import List, Dict, Optional
from anthropic import Anthropic

from prompts.system_prompts import SUMMARY_GENERATION_PROMPT_TEMPLATE
from ai.conversation_utils import format_messages_to_role_string
from config.constants import (
    ANTHROPIC_SUMMARIZER_MODEL,
    OPENAI_SUMMARIZER_MODEL,
    MAX_SUMMARY_TOKENS
)
from loggings import log_debug, log_info, log_error


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
            self.model = ANTHROPIC_SUMMARIZER_MODEL

        elif self.provider == "openai":
            try:
                import openai
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")

            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            self.client = openai.OpenAI(api_key=self.api_key)
            self.model = OPENAI_SUMMARIZER_MODEL

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def generate_summary(self, messages: List[Dict[str, str]], max_tokens: int = MAX_SUMMARY_TOKENS) -> Optional[str]:
        """
        Generate a summary of recent conversation history.

        Args:
            messages: List of message dictionaries to summarize
            max_tokens: Maximum tokens for the summary

        Returns:
            A concise summary of the conversation, or None on failure
        """
        if not messages:
            log_debug("Summarizer: No messages provided for summary")
            return None

        log_info(f"Summarizer: Generating summary for {len(messages)} messages via {self.provider}")
        conversation_text = format_messages_to_role_string(messages)

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

            log_info(f"Summarizer: Summary generated (chars={len(summary)})")
            return summary or None
        except Exception as e:
            print(f"✗ Error generating summary: {e}")
            log_error(f"Summarizer: Error generating summary ({self.provider}): {e}")
            return None
