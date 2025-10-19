#!/usr/bin/env python3
"""AI Planner - Plans response strategy before generating responses"""

import json
import os
import random
import sys
from pathlib import Path
from typing import Dict
from anthropic import Anthropic
from dotenv import load_dotenv

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.conversation_utils import parse_role_format_to_messages
from config.constants import ANTHROPIC_PLANNER_MODEL, MAX_PLANNER_TOKENS
from loggings import log_debug, log_info, log_error

load_dotenv()

# Constants
VALID_INTENTS = ["ack", "ask_followup", "share_story", "reflect", "answer_question"]
VALID_TONES = [
    # Positive & energetic
    "playful", "enthusiastic", "eager", "joyful", "amused", "optimistic", "excited",
    # Caring & emotional
    "caring", "loving", "grateful", "sympathetic", "relieved", "admiring",
    # Confident & assertive 
    "confident", "approving", "curious", "determined", "proud",
    # Thoughtful & nuanced
    "neutral", "reflective", "contemplative", "interested",
    # Vulnerable & authentic
    "worried", "confused", "surprised", "disappointed", "embarrassed",
    # Strong reactions 
    "annoyed", "frustrated", "concerned", "skeptical"
]
VALID_LENGTHS = ["minimal", "short", "medium"]

DEFAULT_PLAN = {
    "should_respond": True,
    "intent": "ack",
    "tone": "neutral",
    "response_length": "short",
    "topic": "general",
    "hint": "be brief and friendly"
}

PLANNING_SYSTEM_PROMPT = """You are a dialogue planner for a family chatbot. The chatbot is having a conversation with its parents (mom and dad) in a family group chat, and responds as their daughter.

Based on the conversation history, plan the response strategy for the latest message.

Return JSON with these fields:
- should_respond: true/false (whether to reply)
- intent: "ack" | "ask_followup" | "share_story" | "reflect" | "answer_question"
- tone: Select the most appropriate tone from these options:
  * Positive & energetic: "playful", "enthusiastic", "eager", "joyful", "amused", "optimistic", "excited"
  * Caring & emotional: "caring", "loving", "grateful", "sympathetic", "relieved", "admiring"
  * Confident & assertive: "confident", "approving", "curious", "determined", "proud"
  * Thoughtful: "neutral", "reflective", "contemplative", "interested"
  * Vulnerable: "worried", "confused", "surprised", "disappointed", "embarrassed"
  * Strong reactions: "annoyed", "frustrated", "concerned", "skeptical"
- response_length: "minimal" | "short" | "medium"
- topic: short noun (e.g., "family", "work")
- hint: one instruction (e.g., "be encouraging", "show confidence", "express gratitude")

Intent guide:
- ack: Simple acknowledgment (use sparingly)
- ask_followup: Ask follow-up question
- share_story: Share related experience
- reflect: Thoughtful response
- answer_question: Message has a question (?, 吗, 呢, 怎么, 什么)

Tone selection guide:
- Match the emotional context of the conversation
- Use confident/assertive tones when sharing opinions or achievements
- Use vulnerable tones when appropriate (shows authenticity)
- Strong reaction tones should be used sparingly and only when contextually appropriate

Response length:
- minimal: 1 short sentence (for simple acks)
- short: 1-2 sentences (default)
- medium: 2-3 sentences (for questions, reflections, stories)

Set should_respond=false for:
- Generic/empty messages (嗯, 好, 哦)
- Already replied to similar content
- Simple greetings already acknowledged

Return only JSON."""


def _extract_json(text: str) -> str:
    """Extract JSON from model response, handling markdown code blocks."""
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end != -1:
            return text[start:end].strip()

    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end != -1:
            return text[start:end].strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        return text[start:end]

    return text.strip()


def _call_model(messages: list, system: str = None) -> str:
    """
    Call Claude API for planning.

    Args:
        messages: List of message dicts with role and content
        system: Optional system prompt
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found")

    client = Anthropic(api_key=api_key)

    params = {
        "model": ANTHROPIC_PLANNER_MODEL,
        "max_tokens": MAX_PLANNER_TOKENS,
        "messages": messages
    }

    if system:
        params["system"] = system

    log_debug(f"Planner: Calling Anthropic planner ({len(messages)} messages, max_tokens={MAX_PLANNER_TOKENS})")
    response = client.messages.create(**params)
    text = response.content[0].text.strip()
    preview = text if len(text) <= 160 else f"{text[:160]}..."
    log_debug(f"Planner: Raw model response preview: {preview}")
    return text


def _validate_plan(plan: Dict) -> Dict:
    """Validate and fix plan structure."""
    # Ensure all required fields exist
    for field in ["should_respond", "intent", "tone", "response_length", "topic", "hint"]:
        if field not in plan:
            plan[field] = DEFAULT_PLAN[field]

    # Convert should_respond to boolean
    if isinstance(plan["should_respond"], str):
        plan["should_respond"] = plan["should_respond"].lower() in ["true", "yes", "1"]
    elif not isinstance(plan["should_respond"], bool):
        plan["should_respond"] = True

    # Validate enum fields
    if plan["intent"] not in VALID_INTENTS:
        plan["intent"] = "ack"
    if plan["tone"] not in VALID_TONES:
        plan["tone"] = "neutral"
    if plan["response_length"] not in VALID_LENGTHS:
        plan["response_length"] = "short"

    return plan


def plan_response(history: str) -> Dict:
    """
    Plan response strategy for a new message.

    Args:
        history: Recent conversation history in [role] format

    Returns:
        Plan dict with should_respond, intent, tone, response_length, topic, hint
    """
    # Use system prompt directly
    system_prompt = PLANNING_SYSTEM_PROMPT

    # Convert history to multi-turn format using shared utility
    messages = parse_role_format_to_messages(history)

    try:
        log_info(f"Planner: Generating plan (history_messages={len(messages)})")
        response = _call_model(messages, system=system_prompt)
        json_str = _extract_json(response)
        plan = json.loads(json_str)
        validated_plan = _validate_plan(plan)
        log_info(
            "Planner: Plan ready "
            f"(respond={validated_plan.get('should_respond')}, "
            f"intent={validated_plan.get('intent')}, "
            f"tone={validated_plan.get('tone')}, "
            f"length={validated_plan.get('response_length')})"
        )
        return validated_plan
    except Exception as e:
        log_error(f"Planner: Failed to generate plan, using default. Error: {e}")
        return DEFAULT_PLAN.copy()


def should_respond_with_plan(plan: Dict) -> bool:
    """
    Decide if bot should respond based on plan.

    Args:
        plan: Planning result from plan_response()

    Returns:
        True if should respond
    """
    # Check plan's decision
    if not plan.get("should_respond", True):
        log_info("Planner decision: skip response (should_respond=false)")
        return False

    # Random filter for minimal acks (50% chance to skip)
    if plan.get("intent") == "ack" and plan.get("response_length") == "minimal":
        respond = random.random() >= 0.5
        log_debug(f"Planner decision: minimal ack gate -> {'respond' if respond else 'skip'}")
        return respond

    return True


if __name__ == "__main__":
    # Simple test
    test_history = "妈咪: 今天天气不错\n我: 是的"
    test_msg = "记得多喝水"

    plan = plan_response(test_history)
    print(f"Plan: {json.dumps(plan, indent=2, ensure_ascii=False)}")
    print(f"Should respond: {should_respond_with_plan(plan)}")
