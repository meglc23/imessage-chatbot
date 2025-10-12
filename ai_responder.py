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
from consts.contacts import CONTACT_ALIASES, get_mom_contacts, get_dad_contacts

# Directly load the knowledge base and system prompt from their respective files
with open("consts/meg_knowledge.py", "r", encoding="utf-8") as f:
    MEG_KNOWLEDGE = f.read()

with open("consts/system_prompt.py", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

def _debug_log(message: str, log_file: str = "logs/bot_log.txt"):
    """Append debug information to the shared bot log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
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
            return None

        if all('id' in msg for msg in messages):
            ordered_messages = sorted(messages, key=lambda msg: msg['id'])
        else:
            ordered_messages = list(messages)

        # Format conversation history using the latest messages
        recent_messages = ordered_messages[-10:]
        latest_message = ordered_messages[-1]
        latest_parent_text = latest_message['text']

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

        # Build prompt with knowledge base
        user_prompt = f"""Here's the recent conversation:

{conversation_history}

Latest message came from: {latest_sender_alias} (relationship: {relationship_hint})
Latest message text: 「{latest_parent_text}」

---

IMPORTANT - Your Personal Knowledge Base (USE SPARINGLY):
{self.knowledge_base}

---

Instructions:
1. **DON'T OVERUSE the knowledge base. For casual chat, respond naturally WITHOUT pulling knowledge** - Only reference it when parents ask SPECIFIC questions, e.g. work, health, plans, etc.
2. **Responses MUST be a single short sentence (ideal ≤ 20字, never more than one sentence)**
3. Be direct and to the point - no over-explaining
4. Don't volunteer extra information unless specifically asked
5. Match Meg's real tone: mature, confident, independent adult daughter - not childishly obedient
6. Avoid overly sweet or submissive responses - speak as an equal, not a child seeking approval
7. If latest sender is mom/mother, address her as "妈咪"; if dad/father, address him as "爸爸". Do NOT confuse their roles.
8. Focus strictly on the latest message; avoid re-answering topics you've already covered unless the parent explicitly asks again.
9. If the latest parent message is just an acknowledgement (e.g., "好呀", "嗯嗯"), keep your reply minimal and do NOT re-open the previous topic unless they mention it.
10. 如果父母只是客套/收尾, 可以随意轻松地换个新话题或结束谈话, 千万别硬聊没内容的话。
11. 回应要紧扣「Latest message text」这句话, 优先解决其中的问题或情绪, 不要倒回去聊更早的话题。
12. 如果无法确切回答对方的提问, 要坦诚说不知道/不确定, 然后轻松地换个新话题或邀请爸妈换个话题聊。

Examples:
- Parent: "在干嘛？" → "在家休息" (DON'T mention detailed schedule from knowledge base)
- Parent: "工作怎么样？" → "挺好的，最近在做Meta AI项目" (Simple, brief)
- Parent: "早" → "早" (ONLY use knowledge when asked)
- Parent: "周末要不要视频？" → "可以啊" (Confident, not overly eager or childish)

Your previous reply (do NOT rehash this unless the latest parent message explicitly asks again): {last_bot_reply or "None"}

Now respond. Be SUPER brief and natural - 1 sentence if possible:"""

        try:
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

            # Always return the response (let AI handle greetings naturally)
            if not reply:
                return None
            self.last_reply = reply
            _debug_log(f"Stored last reply for future avoidance: {reply}")
            return reply

        except Exception as e:
            print(f"✗ Error generating response: {e}")
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

        summary_aware_prompt = f"""最近对话的总结:
{summary}

近期聊天记录:
{conversation_history}

任务:
1. **仔细阅读总结**, 看是否有未回复的问题或待办事项
2. 如果总结中提到有未回复的问题或待办事项, 请简短地回应这些问题 (1句话, ≤20字)
3. 如果没有待办事项或问题, 返回 "SKIP" (不要开启新话题, 这会在后续步骤处理)
4. 保持Meg的语气: 轻松、自然、简洁

你的回复:"""

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

        summary_prompt = f"""以下是你与父母最近的聊天记录。请用中文简要总结这段对话的主要内容和关键信息。

聊天记录:
{conversation_text}

要求:
1. 用2-4句话总结对话的主要话题和关键点
2. 突出重要信息,比如计划、约定、关心的事项等
3. 如果有未回复的问题或待办事项,要特别指出
4. 保持客观简洁,不要添加主观评价
5. 用中文输出

总结:"""

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
最近对话总结:
{summary}

**注意**: 避免重复总结中已讨论过的话题。开启一个全新的、不同的话题。
"""

        startup_prompt = f"""你是Meg, 一位在加州Mountain View工作的独立自信的女儿。
你正在和{audience_label}聊天, 准备主动开启一个全新的轻松话题。
{summary_context}
个人背景 (参考但不要堆砌):
{self.knowledge_base}

要求:
a. 只输出一句简短的中文, 自然口语化, 直接切入话题, 不要重复打招呼。
b. 话题要新颖, 可以结合上面的背景, 例如工作亮点、日常琐事、兴趣计划等。
d. 让对方容易接话, 可以提出轻松的问题或分享一个新的小计划。
e. 控制在20个汉字左右, 不要冗长, 不要使用列表或编号。
f. **如果提供了总结, 确保话题与总结中的内容完全不同。**
"""

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
