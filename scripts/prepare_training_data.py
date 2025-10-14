#!/usr/bin/env python3
"""
Create a high-quality, diverse training dataset from conversation pairs.

Quality improvements:
1. Filter by response quality (remove short/generic responses)
2. Diversity filtering (deduplicate similar responses using embeddings)
3. Prompt quality filtering (clear, diverse prompts)
4. Select top N diverse samples
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set
from collections import Counter
import argparse
import numpy as np


def contains_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


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


def is_generic_response(text: str) -> bool:
    """Check if response is generic/low-quality."""
    text_lower = text.lower().strip()

    # Common generic responses
    generic_patterns = [
        r'^ok\.?$',
        r'^好的?\.?$',
        r'^okay\.?$',
        r'^yes\.?$',
        r'^no\.?$',
        r'^是的?\.?$',
        r'^不是?\.?$',
        r'^嗯\.?$',
        r'^哦\.?$',
        r'^啊\.?$',
    ]

    for pattern in generic_patterns:
        if re.match(pattern, text_lower):
            return True

    return False


def calculate_response_quality_score(pair: Dict[str, Any]) -> float:
    """
    Calculate a quality score for the response.
    Higher score = better quality for training.
    """
    response = pair['user_response']
    prompt = pair['assistant_message']

    score = 0.0

    # Length scoring (prefer substantive responses)
    response_len = len(response)
    if response_len < 5:
        score -= 10  # Very short
    elif response_len < 15:
        score -= 5   # Short
    elif 20 <= response_len <= 200:
        score += 10  # Good length
    elif 200 < response_len <= 500:
        score += 5   # Longer
    else:
        score += 2   # Very long

    # Generic response penalty
    if is_generic_response(response):
        score -= 20

    # Has Chinese (keeping your language style) - HIGH WEIGHT
    if contains_chinese(response):
        score += 20  # Increased from 5 to 20

    # Sentence complexity (multiple sentences = more expressive)
    sentence_markers = len(re.findall(r'[.,!?。！？-]', response))
    score += min(sentence_markers * 2, 10)

    # Question in response (shows engagement)
    if re.search(r'[?？]', response):
        score += 3

    # Explanation markers (shows thoughtfulness)
    explanation_markers = ['因为', '所以', '但是', '不是', 'because', 'but', 'however', '就是']
    for marker in explanation_markers:
        if marker in response:
            score += 2
            break

    # Prompt quality (prefer shorter prompts from ChatGPT)
    prompt_len = len(prompt)
    if prompt_len > 1000:
        score -= 20  # Too long, strongly penalize
    elif prompt_len > 600:
        score -= 10  # Somewhat long
    elif 50 <= prompt_len <= 300:
        score += 15  # Ideal short prompt
    elif 300 < prompt_len <= 600:
        score += 5   # Acceptable length

    # Bonus: Prompt ends with a question (ChatGPT asking user)
    if re.search(r'[?？]\s*$', prompt.strip()):
        score += 10  # High bonus for questions

    return score


def filter_by_quality(
    pairs: List[Dict[str, Any]],
    min_response_length: int = 10,
    max_prompt_length: int = 1000,
    max_response_length: int = 1000,
    chinese_only: bool = True
) -> List[Dict[str, Any]]:
    """Filter pairs by basic quality criteria."""
    filtered = []
    stats = {
        'total': len(pairs),
        'too_short': 0,
        'too_long_prompt': 0,
        'too_long_response': 0,
        'generic': 0,
        'no_chinese': 0,
        'kept': 0
    }

    for pair in pairs:
        response = pair['user_response']
        prompt = pair['assistant_message']

        # Filter: too short
        if len(response) < min_response_length:
            stats['too_short'] += 1
            continue

        # Filter: generic
        if is_generic_response(response):
            stats['generic'] += 1
            continue

        # Filter: no Chinese (if required)
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

        # Add quality score
        pair['quality_score'] = calculate_response_quality_score(pair)
        filtered.append(pair)
        stats['kept'] += 1

    return filtered, stats


def deduplicate_responses(
    pairs: List[Dict[str, Any]],
    similarity_threshold: float = 0.9
) -> List[Dict[str, Any]]:
    """
    Deduplicate very similar responses using simple text similarity.
    For similar responses, keep the one with highest quality score.
    """
    # Group by response text (exact matches)
    response_groups: Dict[str, List[Dict[str, Any]]] = {}

    for pair in pairs:
        response = pair['user_response'].strip().lower()
        if response not in response_groups:
            response_groups[response] = []
        response_groups[response].append(pair)

    # For each group of identical responses, keep the best one
    deduplicated = []
    stats = {
        'original': len(pairs),
        'unique_responses': len(response_groups),
        'removed': 0
    }

    for response_text, group in response_groups.items():
        # Sort by quality score and keep the best
        best_pair = max(group, key=lambda p: p['quality_score'])
        deduplicated.append(best_pair)
        stats['removed'] += len(group) - 1

    return deduplicated, stats


def filter_repetitive_prompts(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove pairs where the prompt appears too many times (keeps variety)."""
    # Count prompt occurrences (first 100 chars as key to handle slight variations)
    prompt_counter = Counter()
    for pair in pairs:
        prompt_key = pair['assistant_message'][:100]
        prompt_counter[prompt_key] += 1

    # Keep pairs where prompt appears less than 5 times, or keep best quality ones
    prompt_seen: Dict[str, int] = {}
    filtered = []

    # Sort by quality score first
    sorted_pairs = sorted(pairs, key=lambda p: p['quality_score'], reverse=True)

    for pair in sorted_pairs:
        prompt_key = pair['assistant_message'][:100]

        # If this prompt appears many times, only keep a few best examples
        if prompt_counter[prompt_key] > 5:
            if prompt_seen.get(prompt_key, 0) >= 2:
                continue  # Skip, we already have 2 examples

        filtered.append(pair)
        prompt_seen[prompt_key] = prompt_seen.get(prompt_key, 0) + 1

    stats = {
        'original': len(pairs),
        'removed': len(pairs) - len(filtered),
        'kept': len(filtered)
    }

    return filtered, stats


def select_top_n_diverse(
    pairs: List[Dict[str, Any]],
    n: int = 1000
) -> List[Dict[str, Any]]:
    """
    Select top N samples with diversity.
    Strategy: Sort by quality, then ensure length diversity.
    """
    if len(pairs) <= n:
        return pairs

    # Categorize by response length
    short = [p for p in pairs if len(p['user_response']) < 50]
    medium = [p for p in pairs if 50 <= len(p['user_response']) < 150]
    long = [p for p in pairs if len(p['user_response']) >= 150]

    # Sort each category by quality
    short.sort(key=lambda p: p['quality_score'], reverse=True)
    medium.sort(key=lambda p: p['quality_score'], reverse=True)
    long.sort(key=lambda p: p['quality_score'], reverse=True)

    # Target distribution: 20% short, 50% medium, 30% long
    n_short = min(len(short), int(n * 0.2))
    n_medium = min(len(medium), int(n * 0.5))
    n_long = min(len(long), int(n * 0.3))

    # Fill remaining slots with highest quality from any category
    selected = short[:n_short] + medium[:n_medium] + long[:n_long]
    remaining = n - len(selected)

    if remaining > 0:
        all_remaining = short[n_short:] + medium[n_medium:] + long[n_long:]
        all_remaining.sort(key=lambda p: p['quality_score'], reverse=True)
        selected.extend(all_remaining[:remaining])

    return selected


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
        default='data/training_data/conversations.json',
        help='Input conversations.json file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/training_data/quality_training_1000.jsonl',
        help='Output file for fine-tuning data'
    )
    parser.add_argument(
        '--n-samples',
        type=int,
        default=1000,
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
    print("\n3. Filtering by quality (removing short/generic responses)...")
    quality_filtered, quality_stats = filter_by_quality(
        all_pairs,
        min_response_length=args.min_response_length,
        chinese_only=not args.all_languages
    )
    print(f"   ✓ Kept {quality_stats['kept']} pairs")
    print(f"     - Removed {quality_stats['too_short']} (too short)")
    print(f"     - Removed {quality_stats['generic']} (generic)")
    print(f"     - Removed {quality_stats['no_chinese']} (no Chinese)")
    print(f"     - Removed {quality_stats['too_long_prompt']} (prompt too long)")
    print(f"     - Removed {quality_stats['too_long_response']} (response too long)")

    # Deduplicate
    print("\n4. Deduplicating similar responses...")
    deduplicated, dedup_stats = deduplicate_responses(quality_filtered)
    print(f"   ✓ Kept {len(deduplicated)} unique responses")
    print(f"     - Removed {dedup_stats['removed']} duplicates")

    # Filter repetitive prompts
    print("\n5. Filtering repetitive prompts...")
    diverse_prompts, prompt_stats = filter_repetitive_prompts(deduplicated)
    print(f"   ✓ Kept {prompt_stats['kept']} diverse prompts")
    print(f"     - Removed {prompt_stats['removed']} repetitive prompts")

    # Sort all by quality score (no diversity selection, pure quality)
    print(f"\n6. Sorting by quality score...")
    sorted_by_quality = sorted(diverse_prompts, key=lambda p: p['quality_score'], reverse=True)
    print(f"   ✓ Sorted {len(sorted_by_quality)} pairs by quality")

    # Select top 500
    top_500 = sorted_by_quality[:500]  # Always 500, not args.n_samples
    print(f"   ✓ Selected top {len(top_500)} samples")

    # Split into tiers
    tier1 = top_500[:50]           # Top 50
    tier2 = top_500[50:200] if len(top_500) >= 200 else []        # 51-200
    tier3 = top_500[200:500] if len(top_500) >= 500 else []       # 201-500

    # Show statistics
    print("\n" + "="*70)
    print("FINAL DATASET STATISTICS")
    print("="*70)
    print(f"Total samples:           {len(top_500)}")

    # Chinese coverage stats
    chinese_count = sum(1 for p in top_500 if contains_chinese(p['user_response']))
    print(f"\nChinese coverage:")
    print(f"  Responses with Chinese: {chinese_count} ({chinese_count/len(top_500)*100:.1f}%)")

    # Response length distribution
    short = sum(1 for p in top_500 if len(p['user_response']) < 50)
    medium = sum(1 for p in top_500 if 50 <= len(p['user_response']) < 150)
    long_ = sum(1 for p in top_500 if len(p['user_response']) >= 150)

    print(f"\nResponse length distribution:")
    print(f"  Short (<50 chars):     {short} ({short/len(top_500)*100:.1f}%)")
    print(f"  Medium (50-150):       {medium} ({medium/len(top_500)*100:.1f}%)")
    print(f"  Long (>150):           {long_} ({long_/len(top_500)*100:.1f}%)")

    # Prompt length distribution
    short_prompt = sum(1 for p in top_500 if len(p['assistant_message']) < 300)
    medium_prompt = sum(1 for p in top_500 if 300 <= len(p['assistant_message']) < 600)
    long_prompt = sum(1 for p in top_500 if len(p['assistant_message']) >= 600)

    print(f"\nPrompt length distribution:")
    print(f"  Short (<300 chars):    {short_prompt} ({short_prompt/len(top_500)*100:.1f}%)")
    print(f"  Medium (300-600):      {medium_prompt} ({medium_prompt/len(top_500)*100:.1f}%)")
    print(f"  Long (>600):           {long_prompt} ({long_prompt/len(top_500)*100:.1f}%)")

    # Quality score distribution
    scores = [p['quality_score'] for p in top_500]
    print(f"\nQuality scores:")
    print(f"  Average:               {np.mean(scores):.1f}")
    print(f"  Min:                   {min(scores):.1f}")
    print(f"  Max:                   {max(scores):.1f}")

    if len(tier2) > 0 and len(tier3) > 0:
        print(f"\nTier breakdown:")
        print(f"  Tier 1 (top 50):       scores {tier1[-1]['quality_score']:.1f} - {tier1[0]['quality_score']:.1f}")
        print(f"  Tier 2 (51-200):       scores {tier2[-1]['quality_score']:.1f} - {tier2[0]['quality_score']:.1f}")
        print(f"  Tier 3 (201-500):      scores {tier3[-1]['quality_score']:.1f} - {tier3[0]['quality_score']:.1f}")

    # Show samples
    print("\n" + "="*70)
    print("SAMPLE PAIRS (top 3 by quality)")
    print("="*70)

    for i, pair in enumerate(top_500[:3], 1):
        print(f"\n[Pair {i}] Quality Score: {pair['quality_score']:.1f}")
        print(f"Prompt ({len(pair['assistant_message'])} chars):")
        print(f"  {pair['assistant_message'][:150]}...")
        print(f"Response ({len(pair['user_response'])} chars):")
        print(f"  {pair['user_response'][:150]}...")

    print("\n" + "="*70)

    # Write output files for each tier
    print(f"\n7. Writing tiered output files...")

    output_path = Path(args.output)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # File names for each tier
    base_name = output_path.stem

    files_to_write = [
        (tier1, output_dir / f"{base_name}_tier1_top50.jsonl", "Tier 1 (Top 50)"),
    ]

    if len(tier2) > 0:
        files_to_write.append((tier2, output_dir / f"{base_name}_tier2_51-200.jsonl", "Tier 2 (51-200)"))

    if len(tier3) > 0:
        files_to_write.append((tier3, output_dir / f"{base_name}_tier3_201-500.jsonl", "Tier 3 (201-500)"))

    files_to_write.append((top_500, output_path, "All 500 samples"))

    for tier_data, file_path, description in files_to_write:
        formatted = prepare_finetuning_format(tier_data)
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in formatted:
                f.write(line + '\n')
        print(f"   ✓ {description}: {file_path.name} ({len(formatted)} examples)")

    print(f"\n{'='*70}")
    print("READY FOR FINE-TUNING")
    print(f"{'='*70}")
    print(f"\nFiles created:")
    for _, file_path, _ in files_to_write:
        print(f"  - {file_path.name}")
    print(f"\nRecommendation: Start with Tier 1 (top 50) for best quality!")
    print(f"\nNext steps:")
    print(f"  openai api fine_tuning.jobs.create \\")
    print(f"    -t data/training_data/{base_name}_tier1_top50.jsonl \\")
    print(f"    -m gpt-3.5-turbo")


if __name__ == '__main__':
    main()
