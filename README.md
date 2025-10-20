# iMessage AI Chatbot

Intelligent chatbot that responds in your personal style.

## Why This Project?

Keeps family chats moving by watching threads, remembering context, and replying in your voice with a training pipeline for custom fine-tuning.

## Features

- 💬 **Natural Responses** - Direct AI generation using your knowledge base and communication style
- 🧾 **Conversation History** - Keeps the latest 40 messages for continuity
- 📊 **Smart Summaries** - Generates conversation summaries to track unanswered questions
- 🤖 **Proactive Topics** - Generates natural conversation starters
- 🔒 **Privacy First** - All sensitive data gitignored

## Quick Start

```bash
git clone <repo>
cd imessage-chatbot
pip install -r requirements.txt
```

- Add an `.env` with `CHAT_NAME`, `BOT_NAME`, `ANTHROPIC_API_KEY`.
- Create `config/contacts.py` and `config/knowledge_base.py` (gitignored) with aliases plus personal context.
- macOS → System Settings → Privacy & Security → Full Disk Access → add Terminal.
- Launch with `python bot.py` (use `caffeinate -dims` beforehand if you need the Mac awake overnight).

## Project Structure

```
├── bot.py                    # Main bot loop
├── imessage_handler.py       # AppleScript bridge
├── ai/
│   ├── prompts.py            # All prompt templates (system & user)
│   ├── responder.py          # Response & summary generation
│   ├── conversation_utils.py # Message formatting utilities
│   └── planner.py            # (deprecated, not used)
├── config/                   # Contacts & knowledge (gitignored)
├── scripts/                  # Data extraction tools
├── tests/                    # Test suite
├── utils/                    # Shared utilities
├── training/                 # Fine-tuning data tooling & datasets
└── data/
    ├── exports/              # Exported data (gitignored)
    └── logs/                 # Archived bot logs (active log: data/logs/bot_log.txt)
```

## Training Data

Use `training/scripts/` to turn exports into JSONL datasets. Drop source files in `training/raw/` and keep cleaned sets such as `imessage_top150.jsonl` in `training/processed/` (both gitignored).

## Testing

```bash
python tests/test_summary.py           # Unit tests for summary & response generation
python tests/test_generate_summary.py  # Live API test for summary generation
python tests/test_connection.py        # Test iMessage connection
```

## Scripts

```bash
# Export messages from iMessage DB
python scripts/parse_thread.py Home 50

# Prepare fine-tuning data from ChatGPT conversations
python training/scripts/prepare_gpt_training_data.py

# Prepare fine-tuning data from iMessage (configure training/thread_names.py first)
python training/scripts/prepare_imessage_training_data.py
```

## Architecture

**Planner removed** - Modern LLMs (GPT-4, Claude 3.5) handle tone, decision-making, and planning through Chain-of-Thought reasoning. The separate planning stage was redundant. Now uses single-stage direct generation with powerful system prompts.

Benefits: Faster (1 API call vs 2), cheaper (half the tokens), more natural responses.

## Customization

- **Tone & style** – edit `ai/prompts.py` (RESPONSE_SYSTEM_PROMPT)
- **Knowledge** – refresh `config/knowledge_base.py`.
- **Contacts** – update `config/contacts.py`
- **Models** – adjust `config/constants.py`

## Troubleshooting

Grant Terminal Full Disk Access if messages fail to load. Confirm `.env` values if the bot stays quiet.

## License

MIT
