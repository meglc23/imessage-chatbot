#!/usr/bin/env python3
"""
AI Responder - Generates responses using AI APIs
"""

import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from anthropic import Anthropic
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Import contact configuration
from config.contacts import CONTACT_ALIASES, get_mom_contacts, get_dad_contacts

# Import prompts
from prompts.system_prompts import (
    SYSTEM_PROMPT,
    RESPONSE_GENERATION_INSTRUCTIONS,
    SUMMARY_RESPONSE_PROMPT_TEMPLATE,
    SUMMARY_GENERATION_PROMPT_TEMPLATE,
    STARTUP_TOPIC_PROMPT_TEMPLATE
)

# Import planner
from ai.planner import plan_response, should_respond_with_plan

# Model configuration
ANTHROPIC_RESPONSE_MODEL = "claude-3-5-haiku-20241022"
OPENAI_RESPONSE_MODEL = "gpt-4"

# Directly load the knowledge base from file
with open("config/knowledge_base.py", "r", encoding="utf-8") as f:
    MEG_KNOWLEDGE = f.read()

def _debug_log(message: str, log_file: str = None):
    """Append debug information to the shared bot log with date-based partitioning."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Use date-based log file if not specified
    if log_file is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = f"logs/bot_log_{date_str}.txt"

    try:
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}]   DEBUG: {message}\n")
    except Exception:
        pass


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
        self.system_prompt = SYSTEM_PROMPT
        self.bot_name = os.getenv("BOT_NAME", "Meg")
        self.last_reply: Optional[str] = None

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

    def alias_sender(self, sender: str) -> str:
        """
        Map raw sender identifiers (emails/names) to preferred display names.
        - User (Meg) → "我"
        - Mom's email → "妈咪"
        - Heuristics for Dad/Mom names in Chinese/English
        """
        if not sender:
            return sender
        key = sender.strip().lower()

        # User aliases
        if key in {"meg", "me", "chen"}:
            return "我"

        # Explicit contact aliases (emails)
        if key in CONTACT_ALIASES:
            return CONTACT_ALIASES[key]

        # Heuristic: Dad / Mom in common variants
        if any(tok in key for tok in ["爸", "爸爸", "dad", "father", "baba"]):
            return "爸爸"
        if any(tok in key for tok in ["妈", "妈妈", "妈咪", "mom", "mother", "mami"]):
            return "妈咪"

        return sender

    def set_system_prompt(self, prompt: str):
        """Set a custom system prompt."""
        self.system_prompt = prompt

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 80
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
            _debug_log("generate_response: No messages provided")
            return None

        if all('id' in msg for msg in messages):
            ordered_messages = sorted(messages, key=lambda msg: msg['id'])
        else:
            ordered_messages = list(messages)

        _debug_log(f"generate_response: Processing {len(ordered_messages)} messages")

        # Format conversation history using the latest messages
        recent_messages = ordered_messages[-10:]
        latest_message = ordered_messages[-1]
        latest_parent_text = latest_message['text']

        _debug_log(f"generate_response: Using {len(recent_messages)} recent messages for context")
        _debug_log(f"generate_response: Latest message from {latest_message.get('sender')}: {latest_parent_text[:100]}")

        has_bot_message = any(
            msg.get('is_from_me')
            or self.alias_sender(msg['sender']) == "我"
            or (msg.get('sender') or "").lower() == self.bot_name.lower()
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
            _debug_log("Appended cached bot reply to history because DB snapshot lacked it.")
            if len(recent_messages) > 10:
                recent_messages = recent_messages[-10:]
        last_bot_reply = None
        for msg in reversed(recent_messages):
            alias = self.alias_sender(msg['sender'])
            sender_raw = msg.get('sender', '')
            _debug_log(
                f"Inspecting message for prior reply detection: sender={sender_raw}, alias={alias}, "
                f"is_from_me={msg.get('is_from_me')}, text={msg.get('text')}"
            )
            if msg.get('is_from_me') or alias == "我" or sender_raw == os.getenv("BOT_NAME"):
                last_bot_reply = msg['text']
                _debug_log(f"Detected previous bot reply (alias={alias}, sender={sender_raw}): {last_bot_reply}")
                break

        if last_bot_reply is None:
            if self.last_reply:
                last_bot_reply = self.last_reply
                _debug_log("No previous bot reply detected in history; falling back to stored last reply")
            else:
                _debug_log("No previous bot reply detected in recent history")

        # Format conversation history, marking reactions distinctly
        conversation_history_lines = []
        for msg in recent_messages:
            sender_alias = self.alias_sender(msg['sender'])
            text = msg['text']
            # Check if this is a reaction
            if msg.get('is_reaction', False):
                conversation_history_lines.append(f"{sender_alias} {text}")
            else:
                conversation_history_lines.append(f"{sender_alias}: {text}")
        conversation_history = "\n".join(conversation_history_lines)

        mom_contacts = {val for val in (
            (get_mom_contacts().get("email") or "").lower(),
            (get_mom_contacts().get("phone") or "").lower()
        ) if val}
        dad_contacts = {val for val in (
            (get_dad_contacts().get("email") or "").lower(),
            (get_dad_contacts().get("phone") or "").lower()
        ) if val}

        latest_sender_raw = (latest_message.get('sender') or "").lower()
        if latest_sender_raw in mom_contacts:
            relationship_hint = "mom"
            latest_sender_alias = "妈咪"
        elif latest_sender_raw in dad_contacts:
            relationship_hint = "dad"
            latest_sender_alias = "爸爸"
        else:
            relationship_hint = "other"
            latest_sender_alias = self.alias_sender(latest_message.get('sender', 'Unknown'))

        _debug_log(f"AI context latest message: sender={latest_message.get('sender')}, text={latest_parent_text}")

        # Use planner to determine response strategy
        _debug_log(f"generate_response: Calling planner with sender_info={relationship_hint}")
        plan = plan_response(
            history=conversation_history,
            new_msg=latest_parent_text,
            sender_info=relationship_hint,
            last_bot_reply=last_bot_reply
        )
        _debug_log(f"generate_response: Planner result -> intent={plan.get('intent')}, tone={plan.get('tone')}, length={plan.get('response_length')}, should_respond={plan.get('should_respond')}")
        _debug_log(f"generate_response: Planner hint -> {plan.get('hint')}")
        
        # Check if we should respond based on the plan
        if not should_respond_with_plan(plan):
            _debug_log("generate_response: Planner determined not to respond - skipping message")
            return None

        _debug_log("generate_response: Planner approved response - proceeding with generation")

        # Build prompt with knowledge base and planning context
        # Map response_length to specific instructions, adjusted by intent
        intent = plan.get('intent', 'ack')
        response_length = plan.get('response_length', 'short')

        if intent == "answer_question":
            length_instructions = {
                "minimal": "Answer briefly in 1-2 sentences. If you don't know, say so honestly and encourage them to explain.",
                "short": "Answer in 1-2 sentences. If uncertain, admit it naturally and invite more context.",
                "medium": "Answer thoughtfully in 2-3 sentences. If you don't have enough info, be honest and ask them to share more."
            }
        else:
            length_instructions = {
                "minimal": "Reply in 1 very short sentence only.",
                "short": "Reply in 1-2 brief sentences.",
                "medium": "Reply in 2-3 sentences, you can be more thoughtful and detailed."
            }
        length_instruction = length_instructions.get(response_length, length_instructions['short'])

        planning_context = f"""
PLANNING CONTEXT:
- Intent: {plan['intent']}
- Tone: {plan['tone']}
- Response Length: {plan['response_length']} ({length_instruction})
- Topic: {plan['topic']}
- Hint: {plan['hint']}
"""
        
        user_prompt = f"""Here's the recent conversation:

{conversation_history}

Latest message came from: {latest_sender_alias} (relationship: {relationship_hint})
Latest message text: 「{latest_parent_text}」

---

IMPORTANT - Your Personal Knowledge Base (USE SPARINGLY):
{self.knowledge_base}

---

{RESPONSE_GENERATION_INSTRUCTIONS}

{planning_context}

Your previous reply (do NOT rehash this unless the latest parent message explicitly asks again): {last_bot_reply or "None"}

Now respond. Be SUPER brief and natural - 1 sentence if possible:"""

        try:
            _debug_log(f"generate_response: Calling {self.provider} API with model={self.model}, max_tokens={max_tokens}")

            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_prompt,
                    messages=[{
                        "role": "user",
                        "content": user_prompt
                    }]
                )
                reply = response.content[0].text.strip()
                _debug_log(f"generate_response: Received response from Anthropic (length={len(reply)} chars)")

            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                reply = response.choices[0].message.content.strip()
                _debug_log(f"generate_response: Received response from OpenAI (length={len(reply)} chars)")

            # Always return the response (let AI handle greetings naturally)
            if not reply:
                _debug_log("generate_response: Empty response received, returning None")
                return None

            self.last_reply = reply
            _debug_log(f"generate_response: SUCCESS - Generated reply: {reply}")
            return reply

        except Exception as e:
            _debug_log(f"generate_response: ERROR - {type(e).__name__}: {str(e)}")
            print(f"✗ Error generating response: {e}")
            return None

    # ------------------------------------------------------------------
    # Conversation summarisation utilities
    # ------------------------------------------------------------------

    def _format_conversation_text(self, messages: List[Dict[str, str]], for_summary: bool = True) -> str:
        """Return a formatted conversation transcript for prompts."""
        lines: List[str] = []
        for msg in messages:
            sender_alias = self.alias_sender(msg.get('sender', ''))
            is_reaction = msg.get('is_reaction')
            text = msg.get('text') or ""

            if is_reaction:
                reaction_display = text or "[Reaction]"
                lines.append(f"{sender_alias} reacted {reaction_display}")
            else:
                lines.append(f"{sender_alias}: {text}")

        if not for_summary:
            # Limit to last 10 lines for response prompts
            lines = lines[-10:]

        return "\n".join(lines)

    def generate_summary(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 180
    ) -> Optional[str]:
        """Summarise the recent conversation in Chinese."""

        if not messages:
            return None

        conversation_text = self._format_conversation_text(messages, for_summary=True)
        prompt = SUMMARY_GENERATION_PROMPT_TEMPLATE.format(conversation_text=conversation_text)

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}]
                )
                summary = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                summary = response.choices[0].message.content.strip()
            else:
                return None

            return summary or None
        except Exception as e:
            print(f"✗ Error generating summary: {e}")
            return None

    def generate_response_with_summary(
        self,
        messages: List[Dict[str, str]],
        summary: str,
        max_tokens: int = 60
    ) -> Optional[str]:
        """Generate a follow-up response using a conversation summary."""

        if not messages or not summary:
            return None

        conversation_history = self._format_conversation_text(messages, for_summary=False)
        prompt = SUMMARY_RESPONSE_PROMPT_TEMPLATE.format(
            summary=summary,
            conversation_history=conversation_history
        )

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}]
                )
                reply = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                reply = response.choices[0].message.content.strip()
            else:
                return None

            if not reply or reply.upper() == "SKIP":
                return None

            return reply
        except Exception as e:
            print(f"✗ Error generating summary response: {e}")
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

        # Use the same formatting logic as generate_response
        if all('id' in msg for msg in messages):
            ordered_messages = sorted(messages, key=lambda msg: msg['id'])
        else:
            ordered_messages = list(messages)

        recent_messages = ordered_messages[-10:]

        # Format conversation history
        conversation_history_lines = []
        for msg in recent_messages:
            sender_alias = self.alias_sender(msg['sender'])
            text = msg['text']
            if msg.get('is_reaction', False):
                conversation_history_lines.append(f"{sender_alias} {text}")
            else:
                conversation_history_lines.append(f"{sender_alias}: {text}")
        conversation_history = "\n".join(conversation_history_lines)

        latest_message = ordered_messages[-1]
        latest_sender_alias = self.alias_sender(latest_message.get('sender', 'Unknown'))
        latest_parent_text = latest_message['text']

        # Detect sender relationship for context
        mom_contacts = {val for val in (
            (get_mom_contacts().get("email") or "").lower(),
            (get_mom_contacts().get("phone") or "").lower()
        ) if val}
        dad_contacts = {val for val in (
            (get_dad_contacts().get("email") or "").lower(),
            (get_dad_contacts().get("phone") or "").lower()
        ) if val}

        latest_sender_raw = (latest_message.get('sender') or "").lower()
        if latest_sender_raw in mom_contacts:
            relationship_hint = "mom"
        elif latest_sender_raw in dad_contacts:
            relationship_hint = "dad"
        else:
            relationship_hint = "other"

        # Find last bot reply
        last_bot_reply = None
        for msg in reversed(recent_messages):
            if msg.get('is_from_me') or self.alias_sender(msg['sender']) == "我":
                last_bot_reply = msg['text']
                break

        # Use planner to determine response strategy
        plan = plan_response(
            history=conversation_history,
            new_msg=latest_parent_text,
            sender_info=relationship_hint,
            last_bot_reply=last_bot_reply
        )
        _debug_log(f"Summary-aware planner result: {plan}")
        
        # Check if we should respond based on the plan
        if not should_respond_with_plan(plan):
            _debug_log("Summary-aware planner determined not to respond")
            return None

        # Build planning context for summary response
        intent = plan.get('intent', 'ack')
        response_length = plan.get('response_length', 'short')

        if intent == "answer_question":
            length_instructions = {
                "minimal": "Answer briefly in 1-2 sentences. If you don't know, say so honestly and encourage them to explain.",
                "short": "Answer in 1-2 sentences. If uncertain, admit it naturally and invite more context.",
                "medium": "Answer thoughtfully in 2-3 sentences. If you don't have enough info, be honest and ask them to share more."
            }
        else:
            length_instructions = {
                "minimal": "Reply in 1 very short sentence only.",
                "short": "Reply in 1-2 brief sentences.",
                "medium": "Reply in 2-3 sentences, you can be more thoughtful and detailed."
            }
        length_instruction = length_instructions.get(response_length, length_instructions['short'])

        planning_context = f"""
PLANNING CONTEXT:
- Intent: {plan['intent']}
- Tone: {plan['tone']}
- Response Length: {plan['response_length']} ({length_instruction})
- Topic: {plan['topic']}
- Hint: {plan['hint']}
"""

        summary_aware_prompt = SUMMARY_RESPONSE_PROMPT_TEMPLATE.format(
            summary=summary,
            conversation_history=conversation_history
        ) + f"\n\n{planning_context}"

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_prompt,
                    messages=[{
                        "role": "user",
                        "content": summary_aware_prompt
                    }]
                )
                reply = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": summary_aware_prompt}
                    ]
                )
                reply = response.choices[0].message.content.strip()
            else:
                return None

            # If AI says to skip, return None
            if reply.upper() == "SKIP" or not reply:
                _debug_log("Summary-aware response: No pending questions, returning None")
                return None

            self.last_reply = reply
            _debug_log(f"Summary-aware response generated: {reply}")
            return reply

        except Exception as e:
            print(f"✗ Error generating summary-aware response: {e}")
            return None


    def generate_startup_topic(self, audience: str = "family", summary: Optional[str] = None, max_tokens: int = 60) -> Optional[str]:
        """
        Generate a fresh conversation starter topic tailored to the audience.

        Args:
            audience: "mom", "dad", "self", or general descriptor
            summary: Optional summary of recent conversation to avoid repeating topics
            max_tokens: Maximum tokens for the generated topic

        Returns:
            A short sentence introducing a new topic, or None on failure.
        """
        audience_map = {
            "mom": "妈咪",
            "dad": "爸爸",
            "self": "爸妈",
            "family": "爸妈",
        }
        audience_label = audience_map.get(audience.lower(), audience if audience else "爸妈")

        # Build prompt with summary context if available
        summary_context = ""
        if summary:
            summary_context = f"""
Recent conversation summary:
{summary}

**Note**: Avoid repeating topics already discussed in the summary. Start a completely new, different topic.
"""

        startup_prompt = STARTUP_TOPIC_PROMPT_TEMPLATE.format(
            audience_label=audience_label,
            summary_context=summary_context,
            knowledge_base=self.knowledge_base
        )

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_prompt,
                    messages=[{
                        "role": "user",
                        "content": startup_prompt
                    }]
                )
                topic = response.content[0].text.strip()
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": startup_prompt}
                    ]
                )
                topic = response.choices[0].message.content.strip()
            else:
                return None

            return topic or None
        except Exception as e:
            print(f"✗ Error generating startup topic: {e}")
            return None

    def should_respond_to_message(self, message: Dict[str, str], bot_name: str) -> bool:
        """
        Determine if the bot should respond to a specific message.

        Args:
            message: Message dictionary
            bot_name: Name of the bot in the chat

        Returns:
            True if bot should consider responding
        """
        text = message['text'].lower()
        sender = message['sender']

        # Don't respond to own messages
        if sender == bot_name:
            return False

        # Always respond if directly mentioned
        if bot_name.lower() in text or '@ai' in text or 'hey bot' in text:
            return True

        # Respond to questions
        if '?' in text:
            return True

        # Otherwise, let the AI decide based on context
        return True


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
