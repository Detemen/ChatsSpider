# -*- coding: utf-8 -*-
"""
Content validation functions for ChatsSpider
Validates language (Russian percentage) and prohibited content
"""

from typing import List, Dict, Tuple
import re


def estimate_russian_percentage(messages: List[Dict]) -> float:
    """
    Estimate percentage of Russian language in messages
    Uses Cyrillic character detection as proxy for Russian

    Args:
        messages: List of message dicts with 'text' field

    Returns:
        Percentage of Russian/Cyrillic text (0-100)
    """
    if not messages:
        return 0.0

    total_chars = 0
    cyrillic_chars = 0

    # Check first 100 messages (performance optimization)
    sample_messages = messages[:100]

    for msg in sample_messages:
        text = msg.get('text', '')
        if not text:
            continue

        # Count alphabetic characters
        for char in text:
            if char.isalpha():
                total_chars += 1
                # Check if character is in Cyrillic range (includes Russian, Ukrainian, etc.)
                if '\u0400' <= char <= '\u04FF':
                    cyrillic_chars += 1

    if total_chars == 0:
        return 0.0

    return (cyrillic_chars / total_chars) * 100


def check_prohibited_content(chat_data: Dict, messages: List[Dict]) -> Tuple[bool, str]:
    """
    Check for prohibited content patterns

    Checks for:
    - ЗСУ/ВСУ donations (Ukrainian military support)
    - Fraud/scam patterns
    - Illegal services

    Args:
        chat_data: Dict with chat metadata (about, pinned_message, etc.)
        messages: List of recent messages

    Returns:
        (is_valid, reason_if_invalid)
        - is_valid: True if no prohibited content found
        - reason: Description of why content is prohibited (empty if valid)
    """
    from categories_config import PROHIBITED_PATTERNS

    # Combine all text to check
    all_text = []

    # Check description/about
    if chat_data.get('about'):
        all_text.append(chat_data['about'].lower())

    # Check pinned message
    if chat_data.get('pinned_message'):
        all_text.append(chat_data['pinned_message'].lower())

    # Check recent messages (sample first 50 for performance)
    for msg in messages[:50]:
        if msg.get('text'):
            all_text.append(msg['text'].lower())

    # Combine all text
    combined_text = ' '.join(all_text)

    # Check for ЗСУ/ВСУ donations (Ukrainian military support)
    зсу_keywords = PROHIBITED_PATTERNS['зсу_донаты']
    зсу_count = sum(1 for kw in зсу_keywords if kw in combined_text)

    # Threshold: multiple mentions suggest active promotion
    if зсу_count >= 3:
        return False, f"Виявлено збори на ЗСУ/ВСУ ({зсу_count} згадок)"

    # Check for fraud/scam patterns
    fraud_keywords = PROHIBITED_PATTERNS['fraud']
    fraud_matches = [kw for kw in fraud_keywords if kw in combined_text]

    if len(fraud_matches) >= 2:
        return False, f"Ознаки шахрайства: {', '.join(fraud_matches[:2])}"

    # Check for illegal services
    illegal_keywords = PROHIBITED_PATTERNS['illegal']
    illegal_matches = [kw for kw in illegal_keywords if kw in combined_text]

    if len(illegal_matches) >= 2:
        return False, f"Нелегальні послуги: {', '.join(illegal_matches[:2])}"

    # All checks passed
    return True, "Немає забороненого контенту"


def validate_chat(chat_data: Dict) -> Dict:
    """
    Full validation: language + prohibited content

    Args:
        chat_data: Dict with chat info including 'recent_messages'

    Returns:
        Dict with validation results:
        {
            'is_valid': bool,              # True if all checks pass
            'language_valid': bool,         # True if >= 80% Russian
            'language_percentage': float,   # Actual percentage
            'content_valid': bool,          # True if no prohibited content
            'rejection_reason': str or None # Reason for rejection
        }
    """
    messages = chat_data.get('recent_messages', [])

    # Language check
    russian_pct = estimate_russian_percentage(messages)
    language_valid = russian_pct >= 80.0

    # Prohibited content check
    content_valid, content_message = check_prohibited_content(chat_data, messages)

    # Overall validation
    is_valid = language_valid and content_valid

    # Rejection reason
    rejection_reason = None
    if not is_valid:
        if not language_valid:
            rejection_reason = f"Недостатньо російської мови: {russian_pct:.0f}% (потрібно ≥80%)"
        else:
            rejection_reason = content_message

    return {
        'is_valid': is_valid,
        'language_valid': language_valid,
        'language_percentage': russian_pct,
        'content_valid': content_valid,
        'rejection_reason': rejection_reason
    }


# Export functions
__all__ = [
    'estimate_russian_percentage',
    'check_prohibited_content',
    'validate_chat',
]
