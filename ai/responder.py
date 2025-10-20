#!/usr/bin/env python3
"""
AI Responder - Generates responses using AI APIs
"""

import os
import sys
from typing import List, Dict, Optional
from dotenv import load_dotenv
from anthropic import Anthropic
from datetime import datetime
from pathlib import Path
from loggings import log_debug, log_info, log_warning, log_error

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file
load_dotenv()

# Import contact configuration
from config.contacts import CONTACT_ALIASES, get_mom_contacts, get_dad_contacts

# Import prompts
from ai.prompts import (
    RESPONSE_SYSTEM_PROMPT,
    SUMMARY_GENERATION_SYSTEM_PROMPT,
    SUMMARY_GENERATION_PROMPT_TEMPLATE,
    STARTUP_TOPIC_SYSTEM_PROMPT,
    STARTUP_TOPIC_PROMPT_TEMPLATE
)

# Import shared conversation utilities
from ai.conversation_utils import (
    format_messages_to_role_string,
    parse_role_format_to_messages,
    get_time_context
)

# Import constants
from config.constants import (
    ANTHROPIC_RESPONSE_MODEL,
    OPENAI_RESPONSE_MODEL,
    DEFAULT_CONTEXT_WINDOW,
    MAX_RESPONSE_TOKENS,
    MAX_STARTUP_TOPIC_TOKENS
)

# Directly load the knowledge base from file
with open("config/knowledge_base.py", "r", encoding="utf-8") as f:
    MEG_KNOWLEDGE = f.read()

class AIResponder:
    def __init__(self, provider: str = "anthropic", api_key: Optional[str] = None):
        """
        Initialize the AI responder.

        Args:
            provider: "anthropic" or "openai"
            api_key: API key for the provider (uses env var if not provided)
        """
        # Use environment variable as default if api_key is None
        if api_key is None:
            if provider.lower() == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")
            elif provider.lower() == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
        self.provider = provider.lower()
        self.knowledge_base = MEG_KNOWLEDGE

        # System prompt template accepts time_context and knowledge_base as parameters
        self.system_prompt_template = RESPONSE_SYSTEM_PROMPT

        self.bot_name = os.getenv("BOT_NAME", "Meg")
        self.last_reply: Optional[str] = None
        self.context_window = int(os.getenv("CONTEXT_WINDOW", str(DEFAULT_CONTEXT_WINDOW)))

        if self.provider == "anthropic":
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment")
            self.client = Anthropic(api_key=self.api_key)
            self.model = ANTHROPIC_RESPONSE_MODEL

        elif self.provider == "openai":
            try:
                import openai
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")

            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            self.client = openai.OpenAI(api_key=self.api_key)
            self.model = OPENAI_RESPONSE_MODEL

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _get_relationship_hint(self, sender: str) -> tuple[str, str]:
        """
        Determine relationship and alias for a sender.

        Returns:
            (relationship_hint, sender_alias) tuple
            - relationship_hint: "mom", "dad", or "other"
            - sender_alias: "妈咪", "爸爸", or aliased name
        """
        mom_contacts = {val for val in (
            (get_mom_contacts().get("email") or "").lower(),
            (get_mom_contacts().get("phone") or "").lower()
        ) if val}
        dad_contacts = {val for val in (
            (get_dad_contacts().get("email") or "").lower(),
            (get_dad_contacts().get("phone") or "").lower()
        ) if val}

        sender_lower = (sender or "").lower()
        if sender_lower in mom_contacts:
            return "mom", "妈咪"
        elif sender_lower in dad_contacts:
            return "dad", "爸爸"
        else:
            # For other senders, try to get Chinese alias from config
            sender_key = (sender or 'Unknown').strip().lower()
            sender_alias = CONTACT_ALIASES.get(sender_key, sender or 'Unknown')
            return "other", sender_alias

    @staticmethod
    def _sanitize_reply(text: Optional[str]) -> Optional[str]:
        """
        Strip leading [assistant] tags from AI output.
        Only used for startup topic generation where we explicitly tell AI not to use labels.
        """
        if not text:
            return text
        cleaned = text.lstrip()
        lower = cleaned.lower()
        if lower.startswith("[assistant]"):
            cleaned = cleaned[len("[assistant]") :].lstrip(" ：:，,")
        return cleaned

    def _format_messages_for_api(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Convert conversation history into Anthropic multi-turn message format.

        Rules:
        - Messages from bot/me → role: "assistant"
        - Messages from others → role: "user" with simple role label [mom]/[dad]/[other]
        - Consecutive messages from real users are merged into one "user" message
        - Returns alternating user/assistant messages
        """
        if not messages:
            return []

        api_messages = []
        pending_user_messages = []

        for msg in messages:
            text = msg['text']
            is_bot = (
                msg.get('is_from_me') or
                (msg.get('sender') or "").lower() == self.bot_name.lower()
            )

            if is_bot:
                # Flush any pending user messages first
                if pending_user_messages:
                    api_messages.append({
                        "role": "user",
                        "content": "\n".join(pending_user_messages)
                    })
                    pending_user_messages = []

                # Add bot message as assistant
                api_messages.append({
                    "role": "assistant",
                    "content": text  # Bot messages don't need sender label
                })
            else:
                # Get simple role identifier
                relationship, _ = self._get_relationship_hint(msg['sender'])

                # Format with simple role label
                if msg.get('is_reaction', False):
                    formatted_text = f"[{relationship}] {text}"
                else:
                    formatted_text = f"[{relationship}] {text}"

                # Accumulate user messages
                pending_user_messages.append(formatted_text)

        # Flush any remaining user messages
        if pending_user_messages:
            api_messages.append({
                "role": "user",
                "content": "\n".join(pending_user_messages)
            })

        # Anthropic API requires messages to start with "user" role
        # If first message is assistant, prepend a user context message
        if api_messages and api_messages[0]["role"] == "assistant":
            api_messages.insert(0, {
                "role": "user",
                "content": "[context] Conversation started"
            })

        return api_messages

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = MAX_RESPONSE_TOKENS
    ) -> Optional[str]:
        """
        Generate a response based on the conversation history.

        Args:
            messages: List of message dictionaries with 'sender' and 'text'.
            max_tokens: Maximum number of tokens for the response.

        Returns:
            The generated response as a string, or None if no response is generated.
        """
        # Ensure messages are in chronological order using database id when available
        if not messages:
            log_debug("Responder: No messages provided to generate_response")
            return None

        if all('id' in msg for msg in messages):
            ordered_messages = sorted(messages, key=lambda msg: msg['id'])
        else:
            ordered_messages = list(messages)

        log_debug(f"Responder: Processing {len(ordered_messages)} messages")

        # Format conversation history using the latest messages
        recent_messages = ordered_messages[-self.context_window:]
        latest_message = ordered_messages[-1]
        latest_parent_text = latest_message['text']

        log_debug(f"Responder: Using {len(recent_messages)} recent messages for context")
        log_debug(
            f"Responder: Latest message from {latest_message.get('sender')}: {latest_parent_text[:100]}"
        )

        has_bot_message = any(
            msg.get('is_from_me') or
            (msg.get('sender') or "").lower() == self.bot_name.lower()
            for msg in recent_messages
        )
        if not has_bot_message and self.last_reply:
            placeholder = {
                'id': (recent_messages[-1]['id'] + 0.1) if recent_messages and isinstance(recent_messages[-1].get('id'), (int, float)) else None,
                'sender': self.bot_name,
                'text': self.last_reply,
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'is_from_me': True
            }
            recent_messages.append(placeholder)
            ordered_messages.append(placeholder)
            log_debug("Responder: Added cached bot reply to compensate for missing DB entry")
            if len(recent_messages) > self.context_window:
                recent_messages = recent_messages[-self.context_window:]

        # Convert to multi-turn API format
        conversation_messages = self._format_messages_for_api(recent_messages)
        log_debug(
            f"Responder: Converted {len(recent_messages)} messages into {len(conversation_messages)} API messages"
        )

        try:
            log_debug(
                f"Responder: Calling {self.provider} API (model={self.model}, max_tokens={max_tokens}, "
                f"messages={len(conversation_messages)})"
            )

            # Inject time context and knowledge base into system prompt
            time_context = get_time_context()
            system_prompt = self.system_prompt_template.format(
                time_context=time_context,
                knowledge_base=self.knowledge_base
            )

            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=conversation_messages
                )
                reply = response.content[0].text.strip()
                log_debug(f"Responder: Received response from Anthropic (chars={len(reply)})")

            elif self.provider == "openai":
                # OpenAI uses different format - combine system with messages
                openai_messages = [{"role": "system", "content": system_prompt}] + conversation_messages
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=openai_messages
                )
                reply = response.choices[0].message.content.strip()
                log_debug(f"Responder: Received response from OpenAI (chars={len(reply)})")

            # Always return the response (let AI handle greetings naturally)
            if not reply:
                log_warning("Responder: Empty response received from provider")
                return None

            self.last_reply = reply
            log_info(f"Responder: Reply ready (chars={len(reply)})")
            return reply

        except Exception as e:
            log_error(f"Responder: Error generating response - {type(e).__name__}: {e}")
            print(f"✗ Error generating response: {e}")
            return None

    # ------------------------------------------------------------------
    # Conversation summarisation utilities
    # ------------------------------------------------------------------

    def generate_summary(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 180
    ) -> Optional[str]:
        """Summarise the recent conversation in Chinese."""

        if not messages:
            return None

        log_info(f"Responder: Generating summary (messages={len(messages)})")
        # Use role string format: [mom], [dad], [assistant]
        conversation_text = format_messages_to_role_string(messages, self.bot_name)
        prompt = SUMMARY_GENERATION_PROMPT_TEMPLATE.format(conversation_text=conversation_text)

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=SUMMARY_GENERATION_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                summary = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": SUMMARY_GENERATION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ]
                )
                summary = response.choices[0].message.content.strip()
            else:
                return None

            if summary:
                log_info(f"Responder: Summary generated (chars={len(summary)})")
            else:
                log_warning("Responder: Provider returned empty summary")
            return summary or None
        except Exception as e:
            print(f"✗ Error generating summary: {e}")
            log_error(f"Responder: Error generating summary - {type(e).__name__}: {e}")
            return None

    def generate_response_with_summary(
        self,
        messages: List[Dict[str, str]],
        summary: str,
        max_tokens: int = 80
    ) -> Optional[str]:
        """
        Generate a response using both conversation history and a summary.
        Prioritizes answering unanswered questions from the summary.

        Args:
            messages: List of message dictionaries with 'sender' and 'text'
            summary: Summary of recent conversation highlighting key points
            max_tokens: Maximum number of tokens for the response

        Returns:
            Response string, or None if no pending questions to answer
        """
        if not messages:
            return None

        log_info(
            f"Responder: Generating summary-aware reply "
            f"(messages={len(messages)}, summary_chars={len(summary)})"
        )

        # Use the same formatting logic as generate_response
        if all('id' in msg for msg in messages):
            ordered_messages = sorted(messages, key=lambda msg: msg['id'])
        else:
            ordered_messages = list(messages)

        recent_messages = ordered_messages[-10:]

        # Convert to multi-turn API format
        conversation_messages = self._format_messages_for_api(recent_messages)

        # Add summary context to the conversation
        if conversation_messages:
            # Prepend summary to first user message
            for i, msg in enumerate(conversation_messages):
                if msg["role"] == "user":
                    conversation_messages[i]["content"] = f"""[Earlier conversation summary: {summary}]

{msg["content"]}"""
                    break
        else:
            # No messages, just provide summary
            conversation_messages.append({
                "role": "user",
                "content": f"""[Conversation summary: {summary}]

If there are unanswered questions above, respond. Otherwise say "SKIP"."""
            })

        try:
            log_debug(f"Summary-aware: Using {len(conversation_messages)} multi-turn messages")

            # Inject time context and knowledge base into system prompt
            time_context = get_time_context()
            system_prompt = self.system_prompt_template.format(
                time_context=time_context,
                knowledge_base=self.knowledge_base
            )

            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=conversation_messages
                )
                reply = response.content[0].text.strip()
            elif self.provider == "openai":
                openai_messages = [{"role": "system", "content": system_prompt}] + conversation_messages
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=openai_messages
                )
                reply = response.choices[0].message.content.strip()
            else:
                return None

            # If AI says to skip, return None
            if not reply or reply.strip().upper() == "SKIP":
                log_info("Responder: Summary-aware path chose to skip reply")
                return None

            self.last_reply = reply
            log_info(f"Responder: Summary-aware reply ready (chars={len(reply)})")
            return reply

        except Exception as e:
            print(f"✗ Error generating summary-aware response: {e}")
            log_error(f"Responder: Error in summary-aware response - {type(e).__name__}: {e}")
            return None


    def generate_startup_topic(
        self,
        recent_messages: Optional[List[Dict]] = None,
        summary: Optional[str] = None,
        max_tokens: int = MAX_STARTUP_TOPIC_TOKENS
    ) -> Optional[str]:
        """
        Generate a fresh conversation starter topic using recent message context.

        Args:
            recent_messages: Optional list of recent messages (last 3) to provide context
            summary: Optional summary of recent conversation to avoid repeating topics
            max_tokens: Maximum tokens for the generated topic

        Returns:
            A short sentence introducing a new topic, or None on failure.
        """
        # Build system prompt with time and summary context
        time_context = get_time_context()

        log_info(
            "Responder: Generating startup topic "
            f"(recent_messages={len(recent_messages) if recent_messages else 0}, "
            f"has_summary={'yes' if summary else 'no'})"
        )

        # Build system prompt with time and knowledge base context
        startup_system_prompt = STARTUP_TOPIC_SYSTEM_PROMPT.format(
            time_context=time_context,
            knowledge_base=self.knowledge_base
        )

        # Build user prompt with summary
        user_prompt = STARTUP_TOPIC_PROMPT_TEMPLATE.format(
            summary_context=f"\n{summary}" if summary else ""
        )

        # Build messages array with recent context
        messages = []

        # Add recent messages as context (if provided)
        if recent_messages:
            # Convert recent messages to multi-turn format
            conversation_context = format_messages_to_role_string(recent_messages[-3:])
            messages = parse_role_format_to_messages(conversation_context)

        # Drop any empty-content messages to satisfy provider requirements
        messages = [
            msg for msg in messages
            if msg.get("content") and msg["content"].strip()
        ]

        # Add user prompt
        if not messages or messages[-1]["role"] == "assistant":
            messages.append({
                "role": "user",
                "content": user_prompt
            })
        else:
            # Prepend to last user message (put prompt before conversation context)
            messages[-1]["content"] = f"{user_prompt}\n\n{messages[-1]['content']}"

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=startup_system_prompt,
                    messages=messages
                )
                topic = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": startup_system_prompt}
                    ] + messages
                )
                topic = response.choices[0].message.content.strip()
            else:
                return None

            if topic:
                sanitized = self._sanitize_reply(topic)
                if sanitized != topic:
                    log_warning(f"Responder: AI included [assistant] tag in startup topic, removed it: '{topic}' -> '{sanitized}'")
                log_info(f"Responder: Startup topic generated (chars={len(sanitized)})")
                return sanitized or None
            else:
                log_warning("Responder: Startup topic generation returned empty text")
            return topic or None
        except Exception as e:
            print(f"✗ Error generating startup topic: {e}")
            log_error(f"Responder: Error generating startup topic - {type(e).__name__}: {e}")
            return None


if __name__ == "__main__":
    # Test the responder
    print("Testing AI Responder...")

    try:
        responder = AIResponder(provider="anthropic")

        # Get contacts from contacts.py
        mom_contact = get_mom_contacts().get("email") or get_mom_contacts().get("phone") or "mom@example.com"
        dad_contact = get_dad_contacts().get("phone") or get_dad_contacts().get("email") or "dad@example.com"

        test_messages = [
            {"sender": dad_contact, "text": "崽，奶奶要我转告你，祝你中秋快乐"},
            {"sender": mom_contact, "text": "昨天爸爸临时组织了一次活动，麻潭山观日落和夜景，不错"},
        ]

        last_sender = test_messages[-1]['sender']
        if last_sender.lower() in ["meg", "me", "chen"]:
            print("爸妈，我来了！")
        else:
            response = responder.generate_response(test_messages)
            if response:
                print(f"\nAI Response: {response}")
            else:
                print("\nAI decided not to respond")

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure to set ANTHROPIC_API_KEY or OPENAI_API_KEY in your environment")
