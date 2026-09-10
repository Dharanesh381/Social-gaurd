"""Factual claim extraction interface and implementations."""

import re
from abc import ABC, abstractmethod


class BaseClaimExtractor(ABC):
    """Abstract interface for extracting verifiable factual statements from raw post text."""

    @abstractmethod
    def extract_claims(self, text: str) -> list[str]:
        """Extract a list of factual claim strings from input text."""


class SimpleClaimExtractor(BaseClaimExtractor):
    """Rule and sentence-boundary based claim extractor.

    Cleans text, splits into candidate sentences, removes opinion markers,
    and identifies verifiable assertion candidates.
    """

    # Phrases indicating subjective opinions rather than verifiable factual claims
    OPINION_MARKERS = [
        r"^i (think|feel|believe|guess|suppose|doubt|wish)",
        r"^in my (opinion|view|perspective)",
        r"^it seems (to me|like)",
        r"^personally",
        r"^maybe",
    ]

    def extract_claims(self, text: str, max_claims: int = 3) -> list[str]:
        if not text or not text.strip():
            return []

        # Remove URLs and extra whitespace
        cleaned = re.sub(r"https?://\S+|www\.\S+", "", text)
        cleaned = re.sub(r"#\w+", "", cleaned)  # Remove hashtags
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned:
            return []

        # Split into candidate sentences by sentence-ending punctuation followed by whitespace or linebreaks
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        candidates: list[str] = []

        for sentence in raw_sentences:
            s = sentence.strip()
            # Filter out very short phrases or long rants
            if len(s.split()) < 3 or len(s) < 15:
                continue

            # Check if sentence starts with subjective opinion markers
            is_opinion = False
            for pattern in self.OPINION_MARKERS:
                if re.search(pattern, s.lower()):
                    is_opinion = True
                    break

            if not is_opinion:
                candidates.append(s)

        # Fallback: if all sentences filtered out, return the cleaned first 200 chars
        if not candidates and len(cleaned) >= 10:
            candidates = [cleaned[:200]]

        return candidates[:max_claims]


claim_extractor = SimpleClaimExtractor()
