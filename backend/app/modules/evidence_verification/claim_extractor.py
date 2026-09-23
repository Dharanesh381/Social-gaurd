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

    Cleans text, strips sensationalist prefixes, splits into candidate sentences,
    removes opinion markers, and generates concise verifiable assertion queries.
    """

    # Phrases indicating subjective opinions rather than verifiable factual claims
    OPINION_MARKERS = [
        r"^i (think|feel|believe|guess|suppose|doubt|wish)",
        r"^in my (opinion|view|perspective)",
        r"^it seems (to me|like)",
        r"^personally",
        r"^maybe",
    ]

    # Common social media clickbait / news alert prefixes to strip
    SENSATIONAL_PREFIXES = [
        r"^(breaking|urgent|alert|shocking|exclusive|just in|report|must share|watch|update|viral)\s*[:!—–-]*\s*",
        r"^(please share|share to save lives|share this)\s*[:!—–-]*\s*",
    ]

    def clean_sentence_prefix(self, sentence: str) -> str:
        """Strip sensationalist alert prefixes from candidate claims."""
        s = sentence.strip()
        for prefix in self.SENSATIONAL_PREFIXES:
            s = re.sub(prefix, "", s, flags=re.IGNORECASE).strip()
        return s

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

        for raw_s in raw_sentences:
            s = self.clean_sentence_prefix(raw_s)
            s = s.strip("\"'“”‘’.,;:!? ")
            
            # Filter out very short phrases or trivial greetings
            if len(s.split()) < 3 or len(s) < 10:
                continue

            # Check if sentence starts with subjective opinion markers
            is_opinion = False
            for pattern in self.OPINION_MARKERS:
                if re.search(pattern, s.lower()):
                    is_opinion = True
                    break

            if not is_opinion:
                # If sentence is excessively long (> 20 words), create a focused claim query
                words = s.split()
                if len(words) > 18:
                    focused = " ".join(words[:16])
                    if focused not in candidates:
                        candidates.append(focused)
                else:
                    if s not in candidates:
                        candidates.append(s)

        # Fallback: if all sentences filtered out, return the cleaned first 150 chars
        if not candidates and len(cleaned) >= 10:
            cleaned_sub = self.clean_sentence_prefix(cleaned)[:150].strip()
            if cleaned_sub:
                candidates = [cleaned_sub]

        return candidates[:max_claims]


claim_extractor = SimpleClaimExtractor()
