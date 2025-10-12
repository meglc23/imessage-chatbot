#!/usr/bin/env python3
"""
Parse messages from chat thread and save to txt file
"""

import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def parse_home_messages(chat_name: str = None, count: int = 1000):
    """
    Extract messages from a specific chat and save to txt file.

    Args:
        chat_name: Name of the chat/thread to parse (defaults to CHAT_NAME from .env)
        count: Number of messages to retrieve
    """
    if chat_name is None:
        chat_name = os.getenv("CHAT_NAME", "TestChat")
    """
    Extract messages from a specific chat and save to txt file.

    Args:
        chat_name: Name of the chat/thread to parse
        count: Number of messages to retrieve
    """
    try:
        # Connect to iMessage database
        db_path = os.path.expanduser("~/Library/Messages/chat.db")
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find the chat
        print(f"\nSearching for chat: '{chat_name}'")
        cursor.execute("""
            SELECT ROWID, display_name, chat_identifier
            FROM chat
            WHERE display_name = ? OR chat_identifier LIKE ?
            LIMIT 1
        """, (chat_name, f"%{chat_name}%"))

        chat_row = cursor.fetchone()
        if not chat_row:
            print(f"✗ Chat '{chat_name}' not found in database")

            # List available chats
            print("\nAvailable chats:")
            cursor.execute("""
                SELECT display_name, chat_identifier
                FROM chat
                WHERE display_name IS NOT NULL OR chat_identifier IS NOT NULL
                ORDER BY ROWID DESC
                LIMIT 20
            """)
            for row in cursor.fetchall():
                print(f"  - {row[0] or row[1]}")

            conn.close()
            return

        chat_id = chat_row[0]
        print(f"✓ Found chat: {chat_row[1] or chat_row[2]} (ID: {chat_id})")

        # Get messages with sender information
        print(f"\nFetching {count} messages...")
        cursor.execute("""
            SELECT
                CASE
                    WHEN message.is_from_me = 1 THEN 'Me'
                    WHEN handle.id IS NOT NULL THEN handle.id
                    ELSE 'Unknown'
                END as sender,
                message.text,
                message.attributedBody,
                datetime(message.date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') as time,
                message.is_from_me
            FROM message
            JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
            LEFT JOIN handle ON message.handle_id = handle.ROWID
            WHERE chat_message_join.chat_id = ?
            ORDER BY message.date DESC
            LIMIT ?
        """, (chat_id, count))

        messages = cursor.fetchall()
        conn.close()

        print(f"✓ Retrieved {len(messages)} messages")

        # Reverse to get chronological order (oldest to newest)
        messages = list(reversed(messages))

        # Write to file
        output_file = f"{chat_name.replace(' ', '_')}_messages.txt"
        print(f"\nWriting to: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"=== Messages from '{chat_name}' ===\n")
            f.write(f"Total messages: {len(messages)}\n")
            f.write(f"Exported on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            for idx, msg in enumerate(messages, 1):
                sender = msg[0]
                text = msg[1]
                time = msg[3]

                # Handle messages without text content
                if not text:
                    if msg[2]:  # attributedBody exists
                        text = "[Attachment or formatted message]"
                    else:
                        text = "[No text content]"

                # Format: [Time] Sender: Message
                f.write(f"[{time}] {sender}:\n")
                f.write(f"{text}\n")
                f.write("-" * 60 + "\n")

        print(f"✓ Successfully exported {len(messages)} messages to {output_file}")

        # Print statistics
        me_count = sum(1 for msg in messages if msg[4] == 1)
        others_count = len(messages) - me_count
        print(f"\nStatistics:")
        print(f"  - Messages from you: {me_count}")
        print(f"  - Messages from others: {others_count}")

        return output_file

    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        if "unable to open database" in str(e):
            print("\n⚠️  Terminal needs 'Full Disk Access' permission!")
            print("   1. Open System Settings > Privacy & Security")
            print("   2. Click 'Full Disk Access'")
            print("   3. Add Terminal.app (or your Python executable)")
            print("   4. Restart Terminal and try again\n")
        return None

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import sys

    # Get chat name and count from command line arguments
    chat_name = sys.argv[1] if len(sys.argv) > 1 else "Home"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    print(f"iMessage Thread Parser")
    print(f"Chat: {chat_name}")
    print(f"Messages to retrieve: {count}")
    print("=" * 60)

    result = parse_home_messages(chat_name, count)

    if result:
        print(f"\n✓ Done! Messages saved to: {result}")
    else:
        print(f"\n✗ Failed to parse messages")
