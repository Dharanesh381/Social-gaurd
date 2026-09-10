"""Text and emoji preprocessing utilities for comment analysis."""

import math
import re

import emoji


def extract_emojis(text: str) -> list[str]:
    """Extract all individual emojis from a string."""
    return [c for c in text if emoji.is_emoji(c)]


def clean_text_for_embedding(text: str) -> str:
    """Normalize text for embedding and semantic comparisons.

    - Strips URLs
    - Normalizes extra whitespaces
    - Keeps casing and punctuation meaningful for transformer models
    """
    if not text:
        return ""
    # Remove URLs
    cleaned = re.sub(r"https?://\S+|www\.\S+", "", text)
    # Remove redundant whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_text_for_exact_match(text: str) -> str:
    """Normalize text for lexical / exact duplicate matching.

    - Lowercases
    - Strips punctuation and emojis
    - Strips whitespace
    """
    if not text:
        return ""
    # Lowercase
    cleaned = text.lower()
    # Remove URLs
    cleaned = re.sub(r"https?://\S+|www\.\S+", "", cleaned)
    # Remove non-alphanumeric (keep spaces)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def compute_emoji_features(comments_text: list[str]) -> dict[str, float]:
    """Calculate emoji presence ratio, total emoji count, and Shannon entropy.

    Returns:
        Dict containing:
        - total_emojis: Total emoji count across all comments
        - emoji_comment_ratio: Proportion of comments containing at least 1 emoji (0.0 to 1.0)
        - emoji_entropy: Shannon entropy across emoji frequencies (0.0 if <=1 distinct emoji)
        - excessive_emoji_ratio: Proportion of comments containing >= 5 emojis
    """
    if not comments_text:
        return {
            "total_emojis": 0.0,
            "emoji_comment_ratio": 0.0,
            "emoji_entropy": 0.0,
            "excessive_emoji_ratio": 0.0,
        }

    total_comments = len(comments_text)
    comments_with_emoji = 0
    excessive_emoji_comments = 0
    emoji_counts: dict[str, int] = {}
    total_emojis = 0

    for text in comments_text:
        emojis = extract_emojis(text)
        count = len(emojis)
        total_emojis += count

        if count > 0:
            comments_with_emoji += 1
        if count >= 5:
            excessive_emoji_comments += 1

        for emo in emojis:
            emoji_counts[emo] = emoji_counts.get(emo, 0) + 1

    # Shannon Entropy: H = -sum(p_i * log2(p_i))
    entropy = 0.0
    if total_emojis > 0:
        for count in emoji_counts.values():
            p_i = count / total_emojis
            entropy -= p_i * math.log2(p_i)

    return {
        "total_emojis": float(total_emojis),
        "emoji_comment_ratio": round(comments_with_emoji / total_comments, 4),
        "emoji_entropy": round(entropy, 4),
        "excessive_emoji_ratio": round(excessive_emoji_comments / total_comments, 4),
    }
