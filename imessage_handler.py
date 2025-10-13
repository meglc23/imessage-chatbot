#!/usr/bin/env python3
"""
iMessage Handler - Handles reading and sending iMessages via AppleScript

Features:
- Read messages from iMessage database
- Send messages using AppleScript
- Detect and include reactions in conversation history (e.g., "❤️", "👍", "😂")
- Reactions appear as "[Reacted ❤️]" or "[Removed reaction ❤️]" in message text
"""

import subprocess
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
from utils.imessage_utils import decode_attributed_body


class iMessageHandler:
    def __init__(self, chat_name: str, user_display_name: str = "Me"):
        """
        Initialize the iMessage handler for a specific chat.

        Args:
            chat_name: The name of the group chat or contact
            user_display_name: Friendly name for messages sent from this machine
        """
        self.chat_name = chat_name
        self.last_message_id = None
        self.user_display_name = user_display_name

    def _get_messages_from_db(self, count: int = 10) -> List[Dict[str, str]]:
        """
        Get messages directly from iMessage database (fallback method).
        """
        try:
            db_path = os.path.expanduser("~/Library/Messages/chat.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get chat GUID
            cursor.execute("""
                SELECT ROWID FROM chat
                WHERE display_name = ? OR chat_identifier = ?
                LIMIT 1
            """, (self.chat_name, self.chat_name))

            chat_row = cursor.fetchone()
            if not chat_row:
                print(f"  ✗ Chat '{self.chat_name}' not found in database")
                conn.close()
                return []

            chat_id = chat_row[0]

            # Get recent messages
            cursor.execute("""
                SELECT
                    message.ROWID as message_id,
                    handle.id as sender,
                    message.text,
                    datetime(
                        message.date/1000000000 + strftime('%s', '2001-01-01'),
                        'unixepoch',
                        'localtime'
                    ) as time,
                    message.is_from_me,
                    message.attributedBody,
                    message.associated_message_guid,
                    message.associated_message_type
                FROM message
                JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
                LEFT JOIN handle ON message.handle_id = handle.ROWID
                WHERE chat_message_join.chat_id = ?
                ORDER BY message.date DESC
                LIMIT ?
            """, (chat_id, count))

            messages = []
            for row in reversed(cursor.fetchall()):  # Reverse to get chronological order
                message_id, sender, text, time_str, is_from_me, attributed_body, associated_guid, associated_type = row

                # Check if this is a reaction (associated_message_type indicates reaction)
                is_reaction = associated_type is not None and associated_type in [2000, 3000]

                if is_reaction:
                    # Parse reaction type from associated_message_type
                    reaction_text = self._parse_reaction(associated_type, text)
                    if reaction_text:
                        if is_from_me:
                            resolved_sender = self.user_display_name
                        else:
                            resolved_sender = sender or "Unknown"

                        messages.append({
                            'id': message_id,
                            'sender': resolved_sender,
                            'text': reaction_text,
                            'time': time_str,
                            'is_from_me': bool(is_from_me),
                            'is_reaction': True
                        })
                else:
                    # Regular message
                    if text is None:
                        text = decode_attributed_body(attributed_body)

                    if is_from_me:
                        resolved_sender = self.user_display_name
                    else:
                        resolved_sender = sender or "Unknown"

                    messages.append({
                        'id': message_id,
                        'sender': resolved_sender,
                        'text': text,
                        'time': time_str,
                        'is_from_me': bool(is_from_me),
                        'is_reaction': False
                    })

            conn.close()
            print(f"  ✓ Retrieved {len(messages)} messages from database")
            return messages

        except Exception as e:
            print(f"  ✗ Database method failed: {e}")
            if "unable to open database" in str(e):
                print("\n  ⚠️  Terminal needs 'Full Disk Access' permission!")
                print("     1. Open System Settings > Privacy & Security")
                print("     2. Click 'Full Disk Access'")
                print("     3. Add Terminal.app (or your Python executable)")
                print("     4. Restart Terminal and try again\n")
            return []

    def _parse_reaction(self, associated_type: int, text: Optional[str]) -> Optional[str]:
        """
        Parse reaction type and return formatted reaction text.

        Args:
            associated_type: The type code from the database (2000-3005 range)
            text: The raw text field (sometimes contains the emoji)

        Returns:
            Formatted reaction string like "[Reacted ❤️]" or None if unknown
        """
        # Reaction type mapping based on iMessage database schema
        # 2000-2005: Added reactions
        # 3000-3005: Removed reactions
        reaction_map = {
            2000: "❤️",  # Love
            2001: "👍",  # Like
            2002: "👎",  # Dislike
            2003: "😂",  # Laugh
            2004: "‼️",  # Emphasize
            2005: "❓",  # Question
            3000: "❤️",  # Removed Love
            3001: "👍",  # Removed Like
            3002: "👎",  # Removed Dislike
            3003: "😂",  # Removed Laugh
            3004: "‼️",  # Removed Emphasize
            3005: "❓",  # Removed Question
        }

        emoji = reaction_map.get(associated_type)
        if not emoji:
            return None

        # Check if this is a removal (3000 range)
        is_removal = associated_type >= 3000

        if is_removal:
            return f"[Removed reaction {emoji}]"
        else:
            return f"[Reacted {emoji}]"

    def send_message(self, message: str) -> bool:
        """
        Send a message to the configured chat using AppleScript.

        Args:
            message: The message text to send

        Returns:
            True if successful, False otherwise
        """
        # Escape special characters for AppleScript
        escaped_message = message.replace('"', '\\"').replace('\\', '\\\\')

        applescript = f'''
        tell application "Messages"
            set targetChat to first chat whose name is "{self.chat_name}"
            send "{escaped_message}" to targetChat
        end tell
        '''

        try:
            subprocess.run(
                ['osascript', '-e', applescript],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✓ Sent message to {self.chat_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to send message: {e.stderr}")
            return False

    def get_recent_messages(self, count: int = 10) -> List[Dict[str, str]]:
        """
        Get recent messages from the chat.

        Args:
            count: Number of recent messages to retrieve

        Returns:
            List of message dictionaries with 'id', 'sender', 'text', and 'time' keys
        """
        return self._get_messages_from_db(count)

    def get_new_messages(self) -> List[Dict[str, str]]:
        """
        Get only new messages since last check.

        Returns:
            List of new message dictionaries
        """
        all_messages = self.get_recent_messages(count=20)

        if not all_messages:
            return []

        latest_id = all_messages[-1]['id']

        if self.last_message_id is None:
            # First run - mark current position but don't process old messages
            self.last_message_id = latest_id
            return []

        new_messages = [msg for msg in all_messages if msg['id'] > self.last_message_id]

        if new_messages:
            self.last_message_id = new_messages[-1]['id']
        else:
            self.last_message_id = latest_id

        return new_messages

    def get_chat_participants(self) -> List[str]:
        """
        Get list of participants in the chat.

        Returns:
            List of participant names
        """
        applescript = f'''
        tell application "Messages"
            set targetChat to first chat whose name is "{self.chat_name}"
            set participantList to participants of targetChat
            set output to ""

            repeat with participant in participantList
                set output to output & name of participant & "\\n"
            end repeat

            return output
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                check=True
            )

            participants = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
            return participants
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to get participants: {e.stderr}")
            return []


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    chat_name = os.getenv("CHAT_NAME", "TestChat")

    # Test the handler
    handler = iMessageHandler(chat_name)

    print(f"Testing iMessage Handler for chat: {chat_name}")
    print("\nRecent messages:")
    messages = handler.get_recent_messages(5)
    for msg in messages:
        print(f"  {msg['sender']}: {msg['text']}")
