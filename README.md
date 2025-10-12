# iMessage AI Chatbot

An AI-powered chatbot that monitors your iMessage chats and responds with your personal tone and style using Claude or GPT.

## Features

- 🤖 Monitors iMessage group chats or individual conversations
- 💬 Generates responses using Anthropic Claude or OpenAI GPT
- 🎭 **Personalized responses** - Uses your personal knowledge base and tone
- 🧠 **Knowledge-aware** - References your personal info only when needed
- 📊 Conversation history analysis for better context
- ⚙️ Customizable system prompts and response behavior

## Requirements

- macOS (uses AppleScript and SQLite to interface with Messages app)
- Python 3.8 or higher
- Anthropic API key (recommended) or OpenAI API key
- **Full Disk Access** permission for Terminal (to read iMessage database)

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the example environment file and configure it:
```bash
cp .env.example .env
```

4. Edit `.env` file with your settings:
   - `CHAT_NAME`: The exact name of your iMessage chat (must match exactly!)
   - `BOT_NAME`: How you want the bot to identify itself
   - `AI_PROVIDER`: Choose "anthropic" or "openai"
   - API Key: Set either `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`

5. **Grant Full Disk Access** (required for reading iMessage database):
   - Open System Settings > Privacy & Security
   - Click "Full Disk Access"
   - Add Terminal.app (or your Python executable)
   - Restart Terminal

6. **Customize your bot's personality**:
   - Edit `consts/meg_knowledge.py` with your personal information
   - Edit `consts/system_prompt.py` to customize the bot's tone and style

## Finding Your Chat Name

To find the exact chat name:

1. Open the Messages app
2. Look at the top of your chat window - the exact text shown there is your chat name
3. For group chats, it's usually something like "Family Group" or the names of participants
4. Copy this exactly into the `CHAT_NAME` setting

## Usage

Run the bot:
```bash
python bot.py
```

The bot will:
1. Monitor the specified chat for new messages
2. Analyze the conversation context
3. Generate and send responses when appropriate
4. Skip responding when it doesn't have anything meaningful to add

Press `Ctrl+C` to stop the bot.

## Configuration Options

Edit `.env` to customize:

- `CHECK_INTERVAL`: How often to check for new messages (default: 10 seconds)
- `BOT_NAME`: The name shown as the sender (should match your iMessage account)
- AI model can be changed in the respective handler files

## Permissions

When you first run the bot, macOS may ask for permissions:
- Allow Terminal/Python to control Messages app
- This is necessary for the AppleScript automation

## Troubleshooting

**"Chat not found" error:**
- Double-check that `CHAT_NAME` exactly matches the chat name in Messages app
- Try putting the full chat name including any special characters

**"API key not found" error:**
- Make sure you created a `.env` file (not `.env.example`)
- Verify your API key is correctly set in the `.env` file

**Messages not sending:**
- Ensure Messages app is open and logged in
- Check that you have granted the necessary permissions

## Project Structure

```
imessage-chatbot/
├── bot.py                    # Main bot script - monitors and responds
├── imessage_handler.py       # Reads/sends messages via AppleScript & SQLite
├── ai_responder.py           # Generates AI responses using Claude/GPT
├── consts/
│   ├── meg_knowledge.py      # Your personal knowledge base
│   └── system_prompt.py      # Bot's personality and tone instructions
├── parse_home_thread.py      # Tool to parse messages from a thread
├── analyze_tone.py           # Analyze message tone patterns
└── .env                      # Configuration (API keys, chat name, etc.)
```

## Customization

### 1. **Personal Knowledge Base** (`consts/meg_knowledge.py`)
Add your personal information that the bot can reference when needed:
- Basic info (name, age, location, work)
- Daily routines and habits
- Common questions and standard responses
- Future plans and goals

**Important**: The bot is configured to use this sparingly - it only references the knowledge base when asked specific questions, not in casual chat.

### 2. **System Prompt** (`consts/system_prompt.py`)
Customize the bot's personality, tone, and communication style:
- How formal/casual to be
- Typical phrases and expressions
- What topics to avoid or emphasize
- Response length preferences

### 3. **Environment Variables** (`.env`)
- `CHAT_NAME`: Which chat to monitor
- `BOT_NAME`: How the bot identifies itself
- `CHECK_INTERVAL`: Polling frequency in seconds
- `AI_PROVIDER`: "anthropic" or "openai"

## Utility Scripts

### Parse Messages from a Thread
Extract messages from any iMessage thread to a text file:
```bash
python parse_home_thread.py "Thread Name" 1000
```

### Analyze Tone
Analyze the tone and patterns in your messages:
```bash
python analyze_tone.py
```

## License

MIT License - feel free to modify and use as you wish!
