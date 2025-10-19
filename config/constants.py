#!/usr/bin/env python3
"""
Application Constants - Fixed configuration values
"""

# ===== AI Model Configuration =====
# Anthropic Models
ANTHROPIC_RESPONSE_MODEL = "claude-3-5-haiku-20241022"  # For generating responses
ANTHROPIC_PLANNER_MODEL = "claude-3-haiku-20240307"     # For planning responses
ANTHROPIC_SUMMARIZER_MODEL = "claude-3-haiku-20240307"  # For conversation summaries

# OpenAI Models
OPENAI_RESPONSE_MODEL = "gpt-4"      # For generating responses
OPENAI_SUMMARIZER_MODEL = "gpt-4"    # For conversation summaries

# ===== Default Configuration Values =====
# These can be overridden by environment variables in .env file

# Conversation history settings
DEFAULT_MAX_HISTORY_SIZE = 40  # Maximum messages to keep in memory
DEFAULT_CONTEXT_WINDOW = 10    # Messages to send to AI API for context
SUMMARY_THRESHOLD = 20         # Use summary when conversation exceeds this many messages

# Timing settings
DEFAULT_CHECK_INTERVAL = 20    # How often to check for new messages (seconds)

# ===== Application Limits =====
# These are hard limits that should not be changed via .env

# Maximum tokens for AI responses
MAX_RESPONSE_TOKENS = 200
MAX_SUMMARY_TOKENS = 300
MAX_STARTUP_TOPIC_TOKENS = 100
MAX_PLANNER_TOKENS = 200
