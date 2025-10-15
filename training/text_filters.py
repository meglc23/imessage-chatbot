"""
Common text filtering and scoring functions for training data preparation.

These functions are shared between ChatGPT and iMessage training data scripts.
"""

import re
from typing import Dict, Any


def contains_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def contains_emoji(text: str) -> bool:
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U00002600-\U000026FF"  # miscellaneous symbols
        "]+",
        flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))


def count_english_words(text: str) -> int:
    english_words = re.findall(r'\b[a-zA-Z]+\b', text)
    return len(english_words)


def is_reaction_message(text: str) -> bool:
    """
    Check if text is a reaction message (iMessage tapback text).
    E.g., "Reacted 🤣 to ...", "Laughed at ...", "Loved ..."

    Note: Uses 'contains' not 'starts with' because reactions can appear
    anywhere in the message text.
    """
    reaction_keywords = [
        'Reacted',
        'reacted',
        'Laughed at',
        'laughed at',
        'Loved',
        'loved',
        'Liked',
        'liked',
        'Disliked',
        'disliked',
        'Emphasized',
        'emphasized',
        'Questioned',
        'questioned'
    ]

    return any(keyword in text for keyword in reaction_keywords)


def calculate_response_quality_score(
    response: str,
    prompt: str,
    data_source: str = 'gpt'
) -> float:
    """
    Calculate a quality score for a response.
    Higher score = better quality for training.

    Args:
        response: The response text to score
        prompt: The prompt/message that triggered the response
        data_source: 'gpt' or 'imessage' - affects scoring weights

    Returns:
        Quality score (float)
    """
    score = 0.0

    # Length scoring (prefer substantive responses)
    # iMessage: longer messages get higher weight
    response_len = len(response)
    if data_source == 'imessage':
        if response_len < 5:
            score -= 10
        elif response_len < 15:
            score -= 5
        elif 20 <= response_len <= 100:
            score += 10
        elif 100 < response_len <= 200:
            score += 15  # Higher weight for longer
        elif 200 < response_len <= 500:
            score += 20  # Even higher for very long
        else:
            score += 15  # Cap at 500+
    else:
        if response_len < 5:
            score -= 10
        elif response_len < 15:
            score -= 5
        elif 20 <= response_len <= 200:
            score += 10
        elif 200 < response_len <= 500:
            score += 5
        else:
            score += 2

    # Has Chinese - HIGH WEIGHT
    if contains_chinese(response):
        score += 20

    # Has emoji (shows expressiveness and personality)
    if contains_emoji(response):
        score += 15

    # Sentence complexity (multiple sentences = more expressive)
    sentence_markers = len(re.findall(r'[.,!?。！？-]', response))
    score += min(sentence_markers * 2, 10)

    # Explanation markers (shows thoughtfulness)
    explanation_markers = ['因为', '所以', '但是', '不是', '就是']
    for marker in explanation_markers:
        if marker in response:
            score += 2
            break
        
    # Prompt ends with a question (only for ChatGPT)
    # In iMessage, prompts are from friends, so questions are common and not special
    if data_source == 'gpt' and re.search(r'[?？]\s*$', prompt.strip()):
        score += 10 

    # Prompt quality (prefer shorter prompts)
    prompt_len = len(prompt)
    if prompt_len > 500:
        score -= 20 
    elif 30 < prompt_len <= 50:
        score += 5  

    return score
