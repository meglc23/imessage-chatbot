#!/usr/bin/env python3
"""Extract only 'Me' messages with actual text content"""

import sys
import os

# Default input file
input_file = 'data/exports/Home_messages.txt'

# Allow command line argument to override
if len(sys.argv) > 1:
    input_file = sys.argv[1]

if not os.path.exists(input_file):
    print(f"Error: File '{input_file}' not found")
    print(f"Usage: python {sys.argv[0]} [path_to_messages.txt]")
    sys.exit(1)

print(f"Reading from: {input_file}\n")

with open(input_file, 'r', encoding='utf-8') as f:
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
