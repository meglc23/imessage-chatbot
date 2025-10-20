#!/usr/bin/env python3
"""
Quick test to see actual AI-generated summary output
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ai.responder import AIResponder
from config.contacts import get_mom_contacts, get_dad_contacts

# Create responder with real API
responder = AIResponder(provider="anthropic")

mom_contact = get_mom_contacts().get("email") or "mom@example.com"
dad_contact = get_dad_contacts().get("phone") or "dad@example.com"

messages = [
    {"id": 1, "sender": mom_contact, "text": "崽，今天天气怎么样？", "is_from_me": False},
    {"id": 2, "sender": "Me", "text": "挺好的，阳光很好", "is_from_me": True},
    {"id": 3, "sender": dad_contact, "text": "工作忙不忙？", "is_from_me": False},
    {"id": 4, "sender": "Me", "text": "还好，最近在做一个新项目", "is_from_me": True},
    {"id": 5, "sender": dad_contact, "text": "周末要不要视频？", "is_from_me": False},
]

print("Generating summary with REAL API call...")
print("="*80)
summary = responder.generate_summary(messages)
print(f"\nGenerated Summary:\n{summary}")
print("="*80)
