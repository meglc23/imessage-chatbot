# iMessage AI Chatbot

Intelligent chatbot that responds in your personal style, powered by Claude AI.

## Why This Project?

Stay connected with your parents even when you're busy. This bot:
- **Monitors** your family chat on iMessage
- **Understands context** from conversation history and reactions
- **Responds naturally** using your personal knowledge and communication style
- **Handles smartly** - answers pending questions or starts fresh topics

## Features

- 🧠 **Smart Planning** - Plans response strategy (intent, tone, length) before replying
- 💬 **Natural Responses** - Uses your knowledge base and communication style
- ❤️ **Reaction Aware** - Recognizes iMessage reactions (❤️, 👍, 😂)
- 📊 **Smart Startup** - Summarizes conversation and addresses unanswered questions
- 🔒 **Privacy First** - All sensitive data gitignored

## Quick Start

### Setup

```bash
# Install
git clone <repo>
cd imessage-chatbot
pip install -r requirements.txt

# Configure .env
CHAT_NAME=Home
BOT_NAME=Meg
ANTHROPIC_API_KEY=your-key
```

### Configuration Files

Create these in `config/`:

**contacts.py:**
```python
PARENT_CONTACTS = {
    "mom": {"email": "mom@example.com", "alias": "妈咪"},
    "dad": {"phone": "+1234567890", "alias": "爸爸"}
}
```

**knowledge_base.py:**
Add your personal info, routines, recent activities, future plans.

### Permissions

System Settings → Privacy & Security → Full Disk Access → Add Terminal

### Run

```bash
python bot.py
```

## Project Structure

```
├── bot.py                    # Main script
├── imessage_handler.py       # iMessage integration
├── ai/
│   ├── planner.py           # Response planning
│   ├── responder.py         # Response generation
│   └── summarizer.py        # Conversation summarization
├── config/                   # Contacts & knowledge (gitignored)
├── prompts/                  # Prompt templates
├── scripts/                  # Data extraction tools
├── tests/                    # Test suite
├── utils/                    # Shared utilities
└── data/exports/            # Exported data (gitignored)
```

## How It Works

**Startup:**
1. Loads config
2. Generates conversation summary
3. Responds to pending questions OR starts fresh topic

**Runtime:**
1. Polls iMessage every 20s
2. **Plans** response (intent, tone, length)
3. **Generates** response using plan
4. Sends via AppleScript

**Planning Layer:**
- `intent`: ack | ask_followup | share_story | reflect | answer_question
- `tone`: playful | caring | neutral | enthusiastic
- `response_length`: minimal | short | medium

## Testing

```bash
python tests/test_planner.py       # Test planner with real messages
python tests/test_connection.py    # Verify setup
python tests/test_ai_responder.py  # Test responses
```

## Scripts

```bash
# Export messages from iMessage DB
python scripts/parse_thread.py Home 50

# Extract your messages only
python scripts/extract_my_messages.py
```

## Customization

- **Tone & style**: Edit `prompts/system_prompts.py`
- **Knowledge**: Update `config/knowledge_base.py` weekly
- **Contacts**: Modify aliases in `config/contacts.py`
- **Models**: Change model versions in `ai/responder.py` and `ai/planner.py` constants:
  - `ANTHROPIC_PLANNER_MODEL` - Default: `claude-3-haiku-20240307` (cheapest)
  - `ANTHROPIC_RESPONSE_MODEL` - Default: `claude-3-5-haiku-20241022` (best value)

## Troubleshooting

**Can't read messages?** Grant Terminal "Full Disk Access" and restart

**No responses?** Check `ANTHROPIC_API_KEY` and `CHAT_NAME` in `.env`

## License

MIT
