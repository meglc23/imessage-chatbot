#!/usr/bin/env python3
"""Extract only 'Me' messages with actual text content"""

with open('Home_messages.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

my_messages = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith('[') and '] Me:' in line:
        # Next line should be the message content
        if i + 1 < len(lines):
            content = lines[i + 1].strip()
            # Skip attachments and empty messages
            if content and content != '------------------------------------------------------------' and '[Attachment' not in content and '[No text content]' not in content:
                my_messages.append(content)
    i += 1

print(f"Found {len(my_messages)} text messages from 'Me'\n")
print("=" * 60)
for idx, msg in enumerate(my_messages, 1):
    print(f"{idx}. {msg}")
    print()
