#!/usr/bin/env python3
"""
Training dataset from iMessage conversations.

Extracts messages from specified threads (group chats and private chats),
filters for your responses, and prepares them in OpenAI fine-tuning format.
"""

import json
import sqlite3
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add training directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.imessage_utils import decode_attributed_body
from text_filters import (
    contains_chinese,
    contains_emoji,
    count_english_words,
    is_reaction_message,
    calculate_response_quality_score
)

# Try to import thread names from training directory
try:
    from thread_names import TRAINING_THREADS, MESSAGES_PER_THREAD
except ImportError:
    print("Error: training/thread_names.py not found.")
    print("Please create this file with your thread configuration.")
    print("See training/thread_names.py.example or README.md for instructions.")
    sys.exit(1)


def extract_messages_from_thread(chat_name: str, count: int = 100) -> List[Dict[str, Any]]:
    """
    Extract messages from a specific iMessage thread.

    Args:
        chat_name: Name of the chat/thread
        count: Number of recent messages to retrieve

    Returns:
        List of message dictionaries with 'sender', 'text', 'time', 'is_from_me'
    """
    try:
        db_path = os.path.expanduser("~/Library/Messages/chat.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find the chat
        cursor.execute("""
            SELECT ROWID FROM chat
            WHERE display_name = ? OR chat_identifier LIKE ?
            LIMIT 1
        """, (chat_name, f"%{chat_name}%"))

        chat_row = cursor.fetchone()
        if not chat_row:
            print(f"  ⊘ Chat '{chat_name}' not found, skipping...")
            conn.close()
            return []

        chat_id = chat_row[0]
        print(f"  ✓ Found chat '{chat_name}'")

        # Get messages
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
                message.is_from_me,
                message.associated_message_type
            FROM message
            JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
            LEFT JOIN handle ON message.handle_id = handle.ROWID
            WHERE chat_message_join.chat_id = ?
            ORDER BY message.date DESC
            LIMIT ?
        """, (chat_id, count))

        messages = []
        for row in reversed(cursor.fetchall()):
            sender, text, attributed_body, time, is_from_me, associated_type = row

            # Skip reactions (database-level check)
            # This filters actual tapback reactions (❤️, 👍, etc.) using the database metadata
            is_reaction = associated_type is not None and associated_type in [2000, 3000]
            if is_reaction:
                continue

            # Handle missing text
            if not text:
                if attributed_body:
                    decoded = decode_attributed_body(attributed_body)
                    text = decoded if decoded else None
                else:
                    text = None

            # Skip messages without text content
            if not text:
                continue

            messages.append({
                'sender': sender,
                'text': text,
                'time': time,
                'is_from_me': bool(is_from_me),
                'thread': chat_name
            })

        conn.close()
        print(f"    Retrieved {len(messages)} messages")
        return messages

    except Exception as e:
        print(f"  ⊘ Error extracting from '{chat_name}': {e}, skipping...")
        return []


def extract_conversation_pairs_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract conversation pairs: other's message → your response.

    Args:
        messages: List of messages from extract_messages_from_thread

    Returns:
        List of conversation pairs
    """
    pairs = []

    for i in range(len(messages) - 1):
        current_msg = messages[i]
        next_msg = messages[i + 1]

        # We want: other person's message → my response
        if not current_msg['is_from_me'] and next_msg['is_from_me']:
            pairs.append({
                'prompt': current_msg['text'],
                'response': next_msg['text'],
                'thread': current_msg['thread'],
                'timestamp': next_msg['time']
            })

    return pairs


def calculate_pair_quality_score(pair: Dict[str, Any]) -> float:
    """
    Wrapper to calculate quality score for a conversation pair.
    Adapts the pair format to the shared function for iMessage data.
    """
    response = pair['response']
    prompt = pair['prompt']
    return calculate_response_quality_score(response, prompt, data_source='imessage')


def filter_by_quality(
    pairs: List[Dict[str, Any]],
    min_response_length: int = 10,
    max_response_length: int = 1000,
    max_english_words: int = 15,
    chinese_only: bool = True
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Filter pairs by quality criteria."""
    filtered = []
    stats = {
        'total': len(pairs),
        'too_short': 0,
        'too_long': 0,
        'no_chinese': 0,
        'too_many_english_words': 0,
        'reaction_message': 0,
        'kept': 0
    }

    for pair in pairs:
        response = pair['response']

        # Filter: reaction messages (text-level check)
        # This filters text like "Reacted 🤣 to..." that sometimes appears as regular messages
        # This is a secondary check in case the database-level check missed anything
        if is_reaction_message(response):
            stats['reaction_message'] += 1
            continue

        # Filter: too short
        if len(response) < min_response_length:
            stats['too_short'] += 1
            continue

        # Filter: no Chinese (if required)
        if chinese_only and not contains_chinese(response):
            stats['no_chinese'] += 1
            continue

        # Filter: too long
        if len(response) > max_response_length:
            stats['too_long'] += 1
            continue

        # Filter: too many English words
        if count_english_words(response) > max_english_words:
            stats['too_many_english_words'] += 1
            continue

        # Add quality score
        pair['quality_score'] = calculate_pair_quality_score(pair)
        filtered.append(pair)
        stats['kept'] += 1

    return filtered, stats


def prepare_finetuning_format(pairs: List[Dict[str, Any]]) -> List[str]:
    """Prepare in OpenAI fine-tuning format."""
    output = []
    for pair in pairs:
        example = {
            "messages": [
                {"role": "user", "content": pair['prompt']},
                {"role": "assistant", "content": pair['response']}
            ]
        }
        output.append(json.dumps(example, ensure_ascii=False))
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Create training dataset from iMessage conversations'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='training/processed/imessage_top150.jsonl',
        help='Output file for fine-tuning data'
    )
    parser.add_argument(
        '--n-samples',
        type=int,
        default=150,
        help='Number of samples to select'
    )
    parser.add_argument(
        '--min-response-length',
        type=int,
        default=10,
        help='Minimum response length'
    )

    args = parser.parse_args()

    print("="*70)
    print("iMESSAGE TRAINING DATA PREPARATION")
    print("="*70)

    # Extract messages from all threads
    print(f"\n1. Extracting messages from {len(TRAINING_THREADS)} threads...")
    all_messages = []
    threads_found = 0
    for thread_name in TRAINING_THREADS:
        messages = extract_messages_from_thread(thread_name, MESSAGES_PER_THREAD)
        if messages:
            threads_found += 1
        all_messages.extend(messages)

    print(f"   ✓ Successfully extracted from {threads_found}/{len(TRAINING_THREADS)} threads")
    print(f"   ✓ Total messages extracted: {len(all_messages)}")

    if not all_messages:
        print("\n✗ No messages found! Please check your thread names in config/thread_names.py")
        return

    # Extract conversation pairs
    print("\n2. Extracting conversation pairs (other → you)...")
    all_pairs = extract_conversation_pairs_from_messages(all_messages)
    print(f"   ✓ Extracted {len(all_pairs)} conversation pairs")

    if not all_pairs:
        print("\n✗ No conversation pairs found!")
        return

    # Filter by quality
    print("\n3. Filtering by quality...")
    quality_filtered, quality_stats = filter_by_quality(
        all_pairs,
        min_response_length=args.min_response_length
    )
    print(f"   ✓ Kept {quality_stats['kept']} pairs")
    print(f"     - Removed {quality_stats['reaction_message']} (reaction messages)")
    print(f"     - Removed {quality_stats['too_short']} (too short)")
    print(f"     - Removed {quality_stats['no_chinese']} (no Chinese)")
    print(f"     - Removed {quality_stats['too_long']} (too long)")
    print(f"     - Removed {quality_stats['too_many_english_words']} (too many English words)")

    if not quality_filtered:
        print("\n✗ No pairs passed quality filtering!")
        return

    # Sort by quality score
    print("\n4. Sorting by quality score...")
    sorted_by_quality = sorted(quality_filtered, key=lambda p: p['quality_score'], reverse=True)
    print(f"   ✓ Sorted {len(sorted_by_quality)} pairs by quality")

    # Select top N
    top_n = sorted_by_quality[:args.n_samples]
    print(f"   ✓ Selected top {len(top_n)} samples")

    # Show statistics
    print("\n" + "="*70)
    print("FINAL DATASET STATISTICS")
    print("="*70)
    print(f"Total samples:           {len(top_n)}")

    # Chinese coverage
    chinese_count = sum(1 for p in top_n if contains_chinese(p['response']))
    print(f"\nChinese coverage:")
    print(f"  Responses with Chinese: {chinese_count} ({chinese_count/len(top_n)*100:.1f}%)")

    # Emoji coverage
    emoji_count = sum(1 for p in top_n if contains_emoji(p['response']))
    print(f"\nEmoji coverage:")
    print(f"  Responses with emoji:   {emoji_count} ({emoji_count/len(top_n)*100:.1f}%)")

    # Quality scores
    scores = [p['quality_score'] for p in top_n]
    print(f"\nQuality scores:")
    print(f"  Average:                {sum(scores)/len(scores):.1f}")
    print(f"  Min:                    {min(scores):.1f}")
    print(f"  Max:                    {max(scores):.1f}")

    # Thread distribution
    thread_counts = {}
    for p in top_n:
        thread = p['thread']
        thread_counts[thread] = thread_counts.get(thread, 0) + 1

    print(f"\nThread distribution:")
    for thread, count in sorted(thread_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {thread}: {count} ({count/len(top_n)*100:.1f}%)")

    # Show samples
    print("\n" + "="*70)
    print("SAMPLE PAIRS (top 3 by quality)")
    print("="*70)

    for i, pair in enumerate(top_n[:3], 1):
        print(f"\n[Pair {i}] Quality Score: {pair['quality_score']:.1f} | Thread: {pair['thread']}")
        print(f"Prompt ({len(pair['prompt'])} chars):")
        print(f"  {pair['prompt'][:150]}...")
        print(f"Response ({len(pair['response'])} chars):")
        print(f"  {pair['response'][:150]}...")

    print("\n" + "="*70)

    # Write output file
    print(f"\n6. Writing output file...")

    output_path = Path(args.output)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    formatted = prepare_finetuning_format(top_n)
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in formatted:
            f.write(line + '\n')

    print(f"   ✓ Written {len(formatted)} examples to {output_path.name}")

    print(f"\n{'='*70}")
    print("READY FOR FINE-TUNING")
    print(f"{'='*70}")
    print(f"\nFile created: {output_path}")


if __name__ == '__main__':
    main()
