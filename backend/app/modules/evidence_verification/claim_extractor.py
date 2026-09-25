"""Factual claim extraction interface and implementations (Phase 4)."""

import re
from abc import ABC, abstractmethod


class BaseClaimExtractor(ABC):
    """Abstract interface for extracting verifiable factual statements from raw post text."""

    @abstractmethod
    def extract_claims(self, text: str) -> list[str]:
        """Extract a list of factual claim strings from input text."""


class SimpleClaimExtractor(BaseClaimExtractor):
    """Rule and NLP pattern-based claim extractor.

    Cleans text, splits into candidate statements, filters greetings, questions,
    subjective opinions, obvious jokes, and conversational filler, and isolates
    meaningful factual claims suitable for fact-checking.
    """

    # Phrases indicating greetings and pleasantries rather than claims
    GREETING_MARKERS = [
        r"^(hello|hi|hey|good\s+(morning|afternoon|evening|day|night)|greetings|welcome|howdy|sup)\b",
        r"^(have\s+a\s+(great|nice|wonderful|good)\s+day)\b",
        r"^(thanks|thank\s+you|cheers)\b",
    ]

    # Phrases indicating subjective opinions rather than verifiable factual claims
    OPINION_MARKERS = [
        r"^(i\s+(think|feel|believe|guess|suppose|doubt|wish|hope|love|hate|prefer))\b",
        r"^(in\s+my\s+(opinion|view|perspective|eyes))\b",
        r"^(it\s+seems\s+(to\s+me|like))\b",
        r"^(personally|maybe|perhaps|probably|to\s+be\s+honest|honestly|imo|imho)\b",
        r"^(my\s+favorite|i\s+like|i\s+dislike)\b",
        r"^(something\s+(we|you|i|everyone|all)\s+(can|should|could|might|must|ought|need))\b",
        r"^(can\s+we\s+all\s+agree|we\s+(can|should|all)\s+(all\s+)?agree)\b",
        r"^(we\s+all\s+know\s+(what|how|why))\b",
        r"^(just\s+(saying|wondering|my\s+two\s+cents|wanted\s+to\s+share))\b",
    ]

    # Obvious jokes, sarcasm, or humor markers
    JOKE_MARKERS = [
        r"\b(just\s+kidding|just\s+a\s+joke|jk|haha|lol|lmao|rofl|sarcasm|sarcastically)\b",
        r"^(why\s+did\s+the|knock\s+knock)\b",
    ]

    # Interrogatives indicating questions
    QUESTION_STARTERS = [
        r"^(what|why|how|who|where|when|which|whose|whom)\b",
        r"^(is\s+(it|this|there|that|he|she))\b",
        r"^(are\s+(they|you|we|there))\b",
        r"^(can\s+(we|anyone|you|someone))\b",
        r"^(could\s+(it|this|we|anyone))\b",
        r"^(does\s+(anyone|it|this))\b",
        r"^(do\s+(you|we|they))\b",
        r"^(should\s+(we|i|they))\b",
        r"^(would\s+(it|you|anyone))\b",
    ]

    # Common social media clickbait / news alert prefixes to strip from claims
    SENSATIONAL_PREFIXES = [
        r"^(breaking|urgent|alert|shocking|exclusive|just in|report|must share|watch|update|viral)\s*[:!—–-]*\s*",
        r"^(please share|share to save lives|share this|spread the word)\s*[:!—–-]*\s*",
    ]

    def clean_sentence_prefix(self, sentence: str) -> str:
        """Strip sensationalist alert prefixes from candidate claims."""
        s = sentence.strip()
        for prefix in self.SENSATIONAL_PREFIXES:
            s = re.sub(prefix, "", s, flags=re.IGNORECASE).strip()
        return s

    def is_non_factual_statement(self, sentence: str, raw_original: str) -> bool:
        """Evaluate if a candidate sentence is a greeting, question, opinion, or joke."""
        lower = sentence.lower().strip()

        # 1. Questions: ends with question mark or begins with question starter
        if raw_original.strip().endswith("?") or lower.endswith("?"):
            return True
        for q_pattern in self.QUESTION_STARTERS:
            if re.search(q_pattern, lower):
                return True

        # 2. Greetings
        for g_pattern in self.GREETING_MARKERS:
            if re.search(g_pattern, lower):
                return True

        # 3. Opinions
        for o_pattern in self.OPINION_MARKERS:
            if re.search(o_pattern, lower):
                return True

        # 4. Obvious jokes / sarcasm
        for j_pattern in self.JOKE_MARKERS:
            if re.search(j_pattern, lower):
                return True

        return False

    def extract_claims(self, text: str, max_claims: int = 3) -> list[str]:
        """Extract verifiable factual statements from text, returning empty list if none found."""
        if not text or not text.strip():
            return []

        # Remove URLs and extra whitespace
        cleaned = re.sub(r"https?://\S+|www\.\S+", "", text)
        cleaned = re.sub(r"#\w+", "", cleaned)  # Remove hashtags
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned:
            return []

        # Split into candidate sentences by sentence-ending punctuation or line breaks
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        candidates: list[str] = []

        for raw_s in raw_sentences:
            s = self.clean_sentence_prefix(raw_s)
            s = s.strip("\"'“”‘’.,;:!? ")

            # Filter out short phrases or trivial length
            if len(s.split()) < 4 or len(s) < 15:
                continue

            # Check if sentence is a non-factual statement (greeting, question, opinion, joke)
            if self.is_non_factual_statement(s, raw_s):
                continue

            # If sentence is excessively long (> 20 words), create a focused query
            words = s.split()
            if len(words) > 18:
                focused = " ".join(words[:16])
                if focused not in candidates:
                    candidates.append(focused)
            else:
                if s not in candidates:
                    candidates.append(s)

        # Do NOT force greetings/opinions into candidates if none were factual.
        # Return only genuine factual claim candidates (up to max_claims).
        return candidates[:max_claims]

    def extract_search_queries(self, claim: str) -> list[str]:
        """Generate high-yield search queries for Google Fact Check API.

        Google Fact Check API yields significantly higher match rates on concise,
        entity-rich keyphrases (3-6 words) rather than lengthy conversational clauses.
        """
        queries: list[str] = [claim.strip()]

        # Strip conversational lead-ins
        lead_ins = [
            r"^(apparently|reportedly|supposedly|allegedly|rumor has it that|sources say that)\s+",
            r"^(viral video shows that|new report claims that|leaked documents reveal that)\s+",
            r"^(did you know that|people are saying that|everyone is talking about)\s+",
            r"^(listen up|look at this|check this out|share this)\s*[:!—–-]*\s*",
        ]
        stripped = claim.strip()
        for p in lead_ins:
            stripped = re.sub(p, "", stripped, flags=re.IGNORECASE).strip()
        if stripped and stripped != claim and stripped not in queries:
            queries.append(stripped)

        # Generate a concise 3-6 word core keyword query by removing common stopwords
        stopwords = {
            "a", "an", "the", "in", "on", "at", "by", "for", "with", "about",
            "against", "between", "into", "through", "during", "before", "after",
            "above", "below", "to", "from", "up", "down", "is", "are", "was",
            "were", "be", "been", "being", "have", "has", "had", "do", "does",
            "did", "will", "would", "shall", "should", "may", "might", "must",
            "can", "could", "that", "this", "these", "those", "it", "its",
            "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
            "not", "only", "own", "same", "than", "too", "very", "s", "t", "just",
            "now", "right", "completely", "all", "out", "of"
        }
        words = re.findall(r"\b[a-zA-Z0-9_-]+\b", stripped)
        content_words = [w for w in words if w.lower() not in stopwords]
        if len(content_words) >= 2:
            core_query = " ".join(content_words[:6])
            if core_query not in queries and len(core_query) > 5:
                queries.append(core_query)

        return queries

    def extract_comment_claims(self, comments: list[Any]) -> list[str]:
        """Extract verifiable claims and fact-check targets mentioned by commenters."""
        extracted: list[str] = []
        fact_checker_cite_pattern = re.compile(
            r"(?:debunked|checked|verified|reported)\s+by\s+([A-Za-z0-9\s.]+?)(?:[:,\-—]|\s+that|\s+as)\s*(.+)",
            re.IGNORECASE,
        )
        url_context_pattern = re.compile(r"(?:factcheck|snopes|reuters|politifact)\.com/[^\s]+", re.IGNORECASE)

        for c in comments:
            txt = getattr(c, "text", "") or ""
            if not txt:
                continue

            # Case A: Comment references a fact check directly: "debunked by Snopes that..."
            m = fact_checker_cite_pattern.search(txt)
            if m:
                claim_part = m.group(2).strip()
                if len(claim_part.split()) >= 3:
                    extracted.append(claim_part[:100])

            # Case B: Comment contains debunking keyword with substantial statement
            lower = txt.lower()
            if any(k in lower for k in ["fake", "debunked", "hoax", "false"]) and not lower.startswith("not fake"):
                clean = re.sub(r"https?://\S+", "", txt).strip()
                # Remove generic exclamations
                clean = re.sub(r"^(this is|it's|that's)\s+(fake|a hoax|false|a lie)[\s!.,-]*", "", clean, flags=re.IGNORECASE).strip()
                if len(clean.split()) >= 3 and len(clean) >= 15:
                    extracted.append(clean[:100])

        return list(dict.fromkeys(extracted))[:3]


claim_extractor = SimpleClaimExtractor()

