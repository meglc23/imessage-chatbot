# iMessage AI Chatbot

Intelligent chatbot that responds in your personal style.

## Why This Project?

Keeps family chats moving by watching threads, remembering context, and replying in your voice with a training pipeline for custom fine-tuning.

## Features

- 🧠 **Smart Planning** - Plans response strategy (intent, tone, length) before replying
- 💬 **Natural Responses** - Uses your knowledge base and communication style
- ❤️ **Reaction Aware** - Recognizes iMessage reactions (❤️, 👍, 😂)
- 📊 **Smart Startup** - Summarizes conversation and addresses unanswered questions
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
- Launch with `python bot.py`.

## Project Structure

```
├── bot.py                    # Main script
├── imessage_handler.py       # AppleScript bridge
├── ai/
│   ├── planner.py           # Response planning
│   ├── responder.py         # Response generation
│   └── summarizer.py        # Conversation summarization
├── config/                   # Contacts & knowledge (gitignored)
├── prompts/                  # Prompt templates
├── scripts/                  # Data extraction tools
├── tests/                    # Test suite
├── utils/                    # Shared utilities
├── training/                 # Fine-tuning data tooling & datasets
└── data/exports/            # Exported data (gitignored)
```

## Training Data

Use `training/scripts/` to turn exports into JSONL datasets. Drop source files in `training/raw/` and keep cleaned sets such as `imessage_top150.jsonl` in `training/processed/` (both gitignored).

## Testing

```bash
python tests/test_planner.py
python tests/test_connection.py
python tests/test_ai_responder.py
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

## Customization

- **Tone & style** – tweak `prompts/system_prompts.py`.
- **Knowledge** – refresh `config/knowledge_base.py`.
- **Contacts** – update aliases in `config/contacts.py`.
- **Models** – adjust constants in `ai/responder.py` and `ai/planner.py`.

## Troubleshooting

Grant Terminal Full Disk Access if messages fail to load. Confirm `.env` values if the bot stays quiet.

## License

MIT
