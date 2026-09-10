"""Hashtag and keyword extraction and Jaccard / Overlap similarity matching."""

import re


def extract_hashtags(text: str, explicit_hashtags: list[str] = None) -> list[str]:
    """Extract and normalize hashtags from text and explicit list."""
    tags: set[str] = set()

    # From explicit list
    if explicit_hashtags:
        for tag in explicit_hashtags:
            cleaned = tag.strip().lower()
            if cleaned:
                tags.add(cleaned if cleaned.startswith("#") else f"#{cleaned}")

    # From raw text
    if text:
        matches = re.findall(r"#\w+", text)
        for m in matches:
            tags.add(m.strip().lower())

    return sorted(list(tags))


def extract_keywords(text: str, min_length: int = 4, max_keywords: int = 15) -> list[str]:
    """Extract salient lowercase keyword tokens, removing common English stopwords."""
    if not text:
        return []

    # Common English stopwords to ignore
    STOPWORDS = {
        "this", "that", "there", "these", "those", "with", "from", "have", "here",
        "about", "would", "could", "should", "their", "where", "which", "while",
        "after", "before", "because", "being", "been", "under", "again", "other",
        "some", "such", "than", "then", "into", "over", "also", "most", "just",
        "more", "when", "what", "will", "your", "only", "very", "even",
    }

    # Remove URLs and non-alphanumeric
    cleaned = re.sub(r"https?://\S+|www\.\S+", "", text.lower())
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)

    tokens = cleaned.split()
    keywords: list[str] = []

    for tok in tokens:
        tok = tok.strip()
        if len(tok) >= min_length and tok not in STOPWORDS and not tok.isdigit():
            if tok not in keywords:
                keywords.append(tok)

    return keywords[:max_keywords]


def compute_jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity index: |A ∩ B| / |A ∪ B|."""
    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))

    if union == 0:
        return 0.0

    return round(float(intersection / union), 4)
