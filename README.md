# iMessage AI Chatbot

An intelligent chatbot that monitors your iMessage conversations with your parents and responds in your personal tone and style, powered by Claude AI.

## Why This Project?

Stay connected with your parents even when you're busy. This bot:
- **Monitors** your family chat on iMessage
- **Understands context** from conversation history and reactions
- **Responds naturally** using your personal knowledge and communication style
- **Handles smartly** - answers pending questions or starts fresh topics based on recent conversation summary

## Key Features

- 📊 **Smart Startup** - Generates conversation summary and addresses unanswered questions
- 💬 **Natural Responses** - Uses your knowledge base and personal tone
- ❤️ **Reaction Aware** - Recognizes iMessage reactions (❤️, 👍, 😂, etc.) as context
- 🔄 **Weekly Updates** - Keep knowledge base current with recent activities
- 🔒 **Privacy First** - All sensitive data protected via .gitignore

## Quick Start

### Prerequisites
- macOS with iMessage
- Python 3.8+
- Anthropic API key ([Get one here](https://console.anthropic.com/))
- Terminal with **Full Disk Access** permission

### Installation

1. **Clone and install dependencies:**
```bash
git clone <your-repo>
cd imessage-chatbot
pip install -r requirements.txt
```

2. **Configure environment** - Create `.env`:
```bash
CHAT_NAME=Home                    # Your iMessage chat name
BOT_NAME=Meg                      # Your name
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-api-key-here
CHECK_INTERVAL=10
```

3. **Set up contacts** - Create `config/contacts.py`:
```python
PARENT_CONTACTS = {
    "mom": {
        "email": "mom@example.com",
        "alias": "妈咪"
    },
    "dad": {
        "phone": "+1234567890",
        "alias": "爸爸"
    }
}

# Helper functions
CONTACT_ALIASES = {
    ident: info["alias"]
    for info in PARENT_CONTACTS.values()
    for ident in (info.get("email"), info.get("phone"))
    if ident
}

def get_mom_contacts():
    return PARENT_CONTACTS["mom"]

def get_dad_contacts():
    return PARENT_CONTACTS["dad"]
```

4. **Personalize knowledge** - Create `config/knowledge_base.py` with your:
   - Personal info (work, location, hobbies)
   - Daily routines
   - Recent activities
   - Future plans

5. **Grant permissions:**
   - System Settings → Privacy & Security → Full Disk Access
   - Add Terminal.app
   - Restart Terminal

### Run

```bash
python bot.py
```

The bot will:
1. Generate conversation summary (last 20 messages)
2. Answer pending questions OR start a fresh topic
3. Monitor chat for new messages
4. Respond naturally when appropriate

## Project Structure

```
imessage-chatbot/
├── bot.py                 # Main bot script
├── imessage_handler.py    # iMessage integration
│
├── ai/                    # AI modules
│   ├── responder.py       # Response generation
│   └── summarizer.py      # Conversation summarization
│
├── config/                # Configuration (gitignored)
│   ├── contacts.py        # Contact info
│   └── knowledge_base.py  # Personal knowledge
│
├── prompts/               # AI prompts
│   └── system_prompts.py  # Prompt templates
│
├── tests/                 # Test suite
├── logs/                  # Logs and utilities
│   └── utils/             # Utility scripts
└── .env                   # Environment config (gitignored)
```

## Customization

### System Prompt
Edit `prompts/system_prompts.py` to customize:
- Tone (formal/casual)
- Response style
- Language preferences
- Typical phrases

### Knowledge Base
Update `config/knowledge_base.py` with:
- Weekly activities
- Current projects
- Plans and goals
- Personal updates

### Contact Aliases
Configure how parents appear in conversation in `config/contacts.py`:
```python
"mom": {"alias": "妈咪"}    # Chinese
"dad": {"alias": "Dad"}     # English
```

## Testing

```bash
# Verify setup
python tests/test_connection.py

# Test AI responses
python tests/test_ai_responder.py

# Test summaries
python tests/test_summary.py
```

## How It Works

**Startup:**
1. Loads config from `.env` and `consts/`
2. Fetches 20 recent messages
3. AI generates conversation summary
4. Identifies unanswered questions
5. Responds to questions OR starts fresh topic

**Runtime:**
1. Polls iMessage DB every 10 seconds
2. Detects new messages & reactions
3. Formats history with aliases
4. Generates contextual response
5. Sends via AppleScript

## Privacy & Security

Protected by `.gitignore`:
- ✅ `.env` - API keys
- ✅ `config/contacts.py` - Personal contacts
- ✅ `config/knowledge_base.py` - Personal data
- ✅ `logs/bot_log.txt` - Conversation logs
- ✅ `.venv/` - Virtual environment

**Before pushing to Git, verify:**
```bash
git status --ignored
```

## Troubleshooting

**Can't read messages?**
- Grant Terminal "Full Disk Access"
- Restart Terminal

**No responses?**
- Check API key in `.env`
- Verify `CHAT_NAME` matches exactly

**Messages not sending?**
- Ensure Messages app is open
- Check permissions

## License

MIT License - Use freely!
