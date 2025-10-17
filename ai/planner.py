#!/usr/bin/env python3
"""AI Planner - Plans response strategy before generating responses"""

import json
import os
import random
from typing import Dict
from anthropic import Anthropic
from datetime import datetime
from dotenv import load_dotenv

from ai.conversation_utils import parse_role_format_to_messages

load_dotenv()

# Model configuration
ANTHROPIC_PLANNER_MODEL = "claude-3-haiku-20240307"

# Constants
VALID_INTENTS = ["ack", "ask_followup", "share_story", "reflect", "answer_question"]
VALID_TONES = ["playful", "caring", "neutral", "enthusiastic"]
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

Context:
{context}

Return JSON with these fields:
- should_respond: true/false (whether to reply)
- intent: "ack" | "ask_followup" | "share_story" | "reflect" | "answer_question"
- tone: "playful" | "caring" | "neutral" | "enthusiastic"
- response_length: "minimal" | "short" | "medium"
- topic: short noun (e.g., "family", "work")
- hint: one instruction (e.g., "be encouraging")

Intent guide:
- ack: Simple acknowledgment (use sparingly)
- ask_followup: Ask follow-up question
- share_story: Share related experience
- reflect: Thoughtful response
- answer_question: Message has a question (?, 吗, 呢, 怎么, 什么)

Response length:
- minimal: 1 short sentence (for simple acks)
- short: 1-2 sentences (default)
- medium: 2-3 sentences (for questions, reflections, stories)

Set should_respond=false for:
- Generic/empty messages (嗯, 好, 哦)
- Already replied to similar content
- Simple greetings already acknowledged

Return only JSON."""


def _get_time_of_day() -> str:
    """Get time of day label."""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    return "evening"


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
        "max_tokens": 200,
        "messages": messages
    }

    if system:
        params["system"] = system

    response = client.messages.create(**params)
    return response.content[0].text.strip()


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
    # Build context
    context_str = [f"Time: {_get_time_of_day()}"]

    # Build system prompt with context
    system_prompt = PLANNING_SYSTEM_PROMPT.format(
        context="\n".join(context_str)
    )

    # Convert history to multi-turn format using shared utility
    messages = parse_role_format_to_messages(history)

    try:
        response = _call_model(messages, system=system_prompt)
        json_str = _extract_json(response)
        plan = json.loads(json_str)
        return _validate_plan(plan)
    except Exception:
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
        return False

    # Random filter for minimal acks (50% chance to skip)
    if plan.get("intent") == "ack" and plan.get("response_length") == "minimal":
        return random.random() >= 0.5

    return True


if __name__ == "__main__":
    # Simple test
    test_history = "妈咪: 今天天气不错\n我: 是的"
    test_msg = "记得多喝水"

    plan = plan_response(test_history)
    print(f"Plan: {json.dumps(plan, indent=2, ensure_ascii=False)}")
    print(f"Should respond: {should_respond_with_plan(plan)}")
