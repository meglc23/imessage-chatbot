#!/usr/bin/env python3
"""
Training dataset from ChatGPT conversation pairs.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from text_filters import (
    contains_chinese,
    count_english_words,
    calculate_response_quality_score
)


def has_image_in_content(content: Dict[str, Any]) -> bool:
    """
    Check if content contains image.

    Args:
        content: Message content dict with 'content_type' and 'parts'

    Returns:
        True if content contains image, False otherwise
    """
    # Check content_type
    content_type = content.get('content_type')
    if content_type and content_type != 'text':
        return True

    # Check parts for image references
    parts = content.get('parts', [])
    for part in parts:
        if isinstance(part, dict):
            if 'image_asset_pointer' in str(part) or part.get('content_type') == 'image_asset_pointer':
                return True

    return False


def extract_conversation_pairs(conversation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract conversation pairs: assistant message → user response."""
    pairs = []
    mapping = conversation.get('mapping', {})

    # Build parent-child relationships
    nodes_by_id = {}
    for node_id, node in mapping.items():
        message = node.get('message')
        if message and message.get('content', {}).get('parts'):
            nodes_by_id[node_id] = {
                'id': node_id,
                'message': message,
                'parent': node.get('parent'),
                'children': node.get('children', [])
            }

    # Find assistant → user pairs
    for node_id, node_data in nodes_by_id.items():
        message = node_data['message']
        author = message.get('author', {})
        content = message.get('content', {})

        if author.get('role') != 'assistant':
            continue

        if has_image_in_content(content):
            continue

        assistant_parts = content.get('parts', [])
        if not assistant_parts:
            continue

        assistant_text = ' '.join(str(part) for part in assistant_parts if part).strip()
        if not assistant_text:
            continue

        # Look for user's response
        children = node_data.get('children', [])
        for child_id in children:
            if child_id not in nodes_by_id:
                continue

            child_node = nodes_by_id[child_id]
            child_message = child_node['message']
            child_author = child_message.get('author', {})

            if child_author.get('role') != 'user':
                continue

            child_content = child_message.get('content', {})

            if has_image_in_content(child_content):
                continue

            user_parts = child_content.get('parts', [])
            if not user_parts:
                continue

            user_text = ' '.join(str(part) for part in user_parts if part).strip()
            if not user_text:
                continue

            pairs.append({
                'assistant_message': assistant_text,
                'user_response': user_text,
                'conversation_title': conversation.get('title', 'Untitled'),
                'timestamp': child_message.get('create_time')
            })

    return pairs


def calculate_pair_quality_score(pair: Dict[str, Any]) -> float:
    """
    Wrapper to calculate quality score for a conversation pair.
    Adapts the pair format to the shared function for ChatGPT data.
    """
    response = pair['user_response']
    prompt = pair['assistant_message']
    return calculate_response_quality_score(response, prompt, data_source='gpt')


def filter_by_quality(
    pairs: List[Dict[str, Any]],
    min_response_length: int = 10,
    max_prompt_length: int = 1000,
    max_response_length: int = 1000,
    chinese_only: bool = True,
    max_english_words: int = 15
) -> List[Dict[str, Any]]:
    """Filter pairs by basic quality criteria."""
    filtered = []
    stats = {
        'total': len(pairs),
        'too_short': 0,
        'too_long_prompt': 0,
        'too_long_response': 0,
        'no_chinese': 0,
        'too_many_english_words': 0,
        'kept': 0
    }

    for pair in pairs:
        response = pair['user_response']
        prompt = pair['assistant_message']

        # Filter: too short
        if len(response) < min_response_length:
            stats['too_short'] += 1
            continue

        # Filter: Chinese only
        if chinese_only and not contains_chinese(response):
            stats['no_chinese'] += 1
            continue

        # Filter: too long
        if len(prompt) > max_prompt_length:
            stats['too_long_prompt'] += 1
            continue

        if len(response) > max_response_length:
            stats['too_long_response'] += 1
            continue

        # Filter: too many English words in user response (allow up to 15 words)
        english_word_count = count_english_words(response)
        if english_word_count > max_english_words:
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
                {"role": "user", "content": pair['assistant_message']},
                {"role": "assistant", "content": pair['user_response']}
            ]
        }
        output.append(json.dumps(example, ensure_ascii=False))
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Create high-quality diverse training dataset'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='training/raw/chatgpt_conversations.json',
        help='Input conversations.json file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='training/processed/chatgpt_top50.jsonl',
        help='Output file for fine-tuning data'
    )
    parser.add_argument(
        '--n-samples',
        type=int,
        default=50,
        help='Number of samples to select'
    )
    parser.add_argument(
        '--min-response-length',
        type=int,
        default=10,
        help='Minimum response length'
    )
    parser.add_argument(
        '--all-languages',
        action='store_true',
        help='Include all languages (default: Chinese only)'
    )

    args = parser.parse_args()

    print("="*70)
    print("HIGH-QUALITY DATASET CREATION")
    print("="*70)

    # Load conversations
    print(f"\n1. Loading conversations from {args.input}...")
    with open(args.input, 'r', encoding='utf-8') as f:
        conversations = json.load(f)
    print(f"   ✓ Found {len(conversations)} conversations")

    # Extract pairs
    print("\n2. Extracting conversation pairs...")
    all_pairs = []
    for conv in conversations:
        pairs = extract_conversation_pairs(conv)
        all_pairs.extend(pairs)
    print(f"   ✓ Extracted {len(all_pairs)} conversation pairs")

    # Filter by quality
    print("\n3. Filtering by quality...")
    quality_filtered, quality_stats = filter_by_quality(
        all_pairs,
        min_response_length=args.min_response_length,
        chinese_only=not args.all_languages
    )
    print(f"   ✓ Kept {quality_stats['kept']} pairs")
    print(f"     - Removed {quality_stats['too_short']} (too short, also filters generic responses)")
    print(f"     - Removed {quality_stats['no_chinese']} (no Chinese)")
    print(f"     - Removed {quality_stats['too_long_prompt']} (prompt too long)")
    print(f"     - Removed {quality_stats['too_long_response']} (response too long)")
    print(f"     - Removed {quality_stats['too_many_english_words']} (too many English words in response)")

    # Sort all by quality score
    print(f"\n4. Sorting by quality score...")
    sorted_by_quality = sorted(quality_filtered, key=lambda p: p['quality_score'], reverse=True)
    print(f"   ✓ Sorted {len(sorted_by_quality)} pairs by quality")

    # Select top 50
    top_50 = sorted_by_quality[:50]  # Only top 50
    print(f"   ✓ Selected top {len(top_50)} samples")

    # Show statistics
    print("\n" + "="*70)
    print("FINAL DATASET STATISTICS")
    print("="*70)
    print(f"Total samples:           {len(top_50)}")

    # Chinese coverage stats
    chinese_count = sum(1 for p in top_50 if contains_chinese(p['user_response']))
    print(f"\nChinese coverage:")
    print(f"  Responses with Chinese: {chinese_count} ({chinese_count/len(top_50)*100:.1f}%)")

    # Response length distribution
    short = sum(1 for p in top_50 if len(p['user_response']) < 50)
    medium = sum(1 for p in top_50 if 50 <= len(p['user_response']) < 150)
    long_ = sum(1 for p in top_50 if len(p['user_response']) >= 150)

    print(f"\nResponse length distribution:")
    print(f"  Short (<50 chars):     {short} ({short/len(top_50)*100:.1f}%)")
    print(f"  Medium (50-150):       {medium} ({medium/len(top_50)*100:.1f}%)")
    print(f"  Long (>150):           {long_} ({long_/len(top_50)*100:.1f}%)")

    # Prompt length distribution
    short_prompt = sum(1 for p in top_50 if len(p['assistant_message']) < 300)
    medium_prompt = sum(1 for p in top_50 if 300 <= len(p['assistant_message']) < 600)
    long_prompt = sum(1 for p in top_50 if len(p['assistant_message']) >= 600)

    print(f"\nPrompt length distribution:")
    print(f"  Short (<300 chars):    {short_prompt} ({short_prompt/len(top_50)*100:.1f}%)")
    print(f"  Medium (300-600):      {medium_prompt} ({medium_prompt/len(top_50)*100:.1f}%)")
    print(f"  Long (>600):           {long_prompt} ({long_prompt/len(top_50)*100:.1f}%)")

    # Quality score distribution
    scores = [p['quality_score'] for p in top_50]
    print(f"\nQuality scores:")
    print(f"  Average:               {sum(scores)/len(scores):.1f}")
    print(f"  Min:                   {min(scores):.1f}")
    print(f"  Max:                   {max(scores):.1f}")

    # Show samples
    print("\n" + "="*70)
    print("SAMPLE PAIRS (top 3 by quality)")
    print("="*70)

    for i, pair in enumerate(top_50[:3], 1):
        print(f"\n[Pair {i}] Quality Score: {pair['quality_score']:.1f}")
        print(f"Prompt ({len(pair['assistant_message'])} chars):")
        print(f"  {pair['assistant_message'][:150]}...")
        print(f"Response ({len(pair['user_response'])} chars):")
        print(f"  {pair['user_response'][:150]}...")

    print("\n" + "="*70)

    # Write output file
    print(f"\n6. Writing output file...")

    output_path = Path(args.output)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    files_to_write = [
        (top_50, output_path, "Top 50 samples"),
    ]

    for tier_data, file_path, description in files_to_write:
        formatted = prepare_finetuning_format(tier_data)
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in formatted:
                f.write(line + '\n')
        print(f"   ✓ {description}: {file_path.name} ({len(formatted)} examples)")

    print(f"\n{'='*70}")
    print("READY FOR FINE-TUNING")
    print(f"{'='*70}")
    print(f"\nFile created: {output_path.name}")


if __name__ == '__main__':
    main()
