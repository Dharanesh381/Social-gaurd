"""Rating normalization and source credibility scoring rules."""

import re

# ==============================================================================
# 1. RATING NORMALIZATION
# ==============================================================================

# Explicit textual mapping from heterogeneous fact-checker verdicts to a normalized float score [0.0 - 1.0]
# 1.0 = True / Supported, 0.0 = False / Contradicted, 0.5 = Mixed / Half True
RATING_MAP = {
    # True / Supported terms
    "true": 1.0,
    "correct": 1.0,
    "accurate": 1.0,
    "mostly true": 0.85,
    "mostly correct": 0.85,
    "verified": 1.0,
    "supported": 1.0,
    
    # False / Contradicted terms
    "false": 0.0,
    "fake": 0.0,
    "incorrect": 0.0,
    "mostly false": 0.15,
    "mostly incorrect": 0.15,
    "debunked": 0.0,
    "pants on fire": 0.0,
    "four pinocchios": 0.0,
    "three pinocchios": 0.15,
    "unproven": 0.35,
    "hoax": 0.0,
    "scam": 0.0,
    
    # Mixed / Misleading terms
    "half true": 0.5,
    "half false": 0.5,
    "mixed": 0.5,
    "misleading": 0.25,
    "missing context": 0.4,
    "out of context": 0.3,
    "altered": 0.1,
    "manipulated": 0.1,
    "partly false": 0.25,
    "partially correct": 0.6,
    "inconclusive": 0.5,
}


def normalize_fact_check_rating(raw_rating: str) -> tuple[float, str]:
    """Normalize heterogeneous raw fact-check textual ratings to [0.0, 1.0] scale.

    Returns:
        Tuple[normalized_score: float, category: str]
        Category is one of: 'TRUE', 'MOSTLY_TRUE', 'MIXED', 'MOSTLY_FALSE', 'FALSE'
    """
    if not raw_rating:
        return 0.5, "MIXED"

    clean_rating = raw_rating.strip().lower()

    # Exact dictionary match
    if clean_rating in RATING_MAP:
        score = RATING_MAP[clean_rating]
    else:
        # Fuzzy keyword matching
        if re.search(r"\b(pants on fire|four pinocchios|fake|hoax|false|incorrect|debunked)\b", clean_rating):
            score = 0.0
        elif re.search(r"\b(mostly false|misleading|out of context|altered|manipulated)\b", clean_rating):
            score = 0.2
        elif re.search(r"\b(half true|mixed|inconclusive|partly)\b", clean_rating):
            score = 0.5
        elif re.search(r"\b(mostly true|mostly correct)\b", clean_rating):
            score = 0.85
        elif re.search(r"\b(true|correct|accurate|verified)\b", clean_rating):
            score = 1.0
        else:
            # Neutral / Inconclusive fallback
            score = 0.5

    if score >= 0.95:
        category = "TRUE"
    elif score >= 0.70:
        category = "MOSTLY_TRUE"
    elif score >= 0.35:
        category = "MIXED"
    elif score >= 0.10:
        category = "MOSTLY_FALSE"
    else:
        category = "FALSE"

    return score, category


# ==============================================================================
# 2. SOURCE CREDIBILITY SCORING
# ==============================================================================

# High-trust IFCN (International Fact-Checking Network) certified publishers
REPUTABLE_PUBLISHERS: dict[str, float] = {
    "snopes": 0.95,
    "snopes.com": 0.95,
    "reuters": 0.98,
    "reuters fact check": 0.98,
    "associated press": 0.98,
    "ap news": 0.98,
    "ap fact check": 0.98,
    "politifact": 0.95,
    "factcheck.org": 0.95,
    "bbc reality check": 0.95,
    "bbc": 0.95,
    "washington post fact checker": 0.92,
    "afp fact check": 0.95,
    "full fact": 0.92,
    "lead stories": 0.90,
    "check your fact": 0.85,
    "the quint": 0.88,
    "alt news": 0.90,
    "boom live": 0.90,
    "vishwas news": 0.88,
}


def compute_source_credibility(publisher_name: str, site_url: str = "") -> float:
    """Evaluate domain credibility for the fact-checking publisher (0.0 to 1.0).

    Uses transparent matching against accredited IFCN organizations with a standard fallback.
    """
    if not publisher_name:
        return 0.70  # Standard baseline for unknown indexed sources

    norm_name = publisher_name.strip().lower()

    for key, score in REPUTABLE_PUBLISHERS.items():
        if key in norm_name:
            return score

    if site_url:
        norm_url = site_url.strip().lower()
        for key, score in REPUTABLE_PUBLISHERS.items():
            if key in norm_url:
                return score
        return 0.75

    return 0.70
