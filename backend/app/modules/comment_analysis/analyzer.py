import re
from typing import Any

from app.modules.comment_analysis.preprocessing import (
    clean_text_for_embedding,
    compute_emoji_features,
    normalize_text_for_exact_match,
)
from app.modules.comment_analysis.similarity import (
    compute_semantic_similarity_features,
)
from app.modules.comment_analysis.temporal import (
    compute_temporal_features,
)
from app.schemas.domain_models import Comment
from app.utils.logging import logger

# Crowdsourced debunking & skepticism patterns in social media comments
DEBUNK_REGEX = re.compile(
    r"\b(fake|fake\s*news|debunked|debunk|false|hoax|scam|scammer|bullshit|bs|misleading|"
    r"not\s*true|untrue|fabricated|disinformation|misinformation|lie|lies|lying|staged|"
    r"cgi|deepfake|ai\s*generated|photoshop(ped)?|clickbait|phishing|manipulated)\b|"
    r"\b(community\s*note)\b|"
    r"(?:debunked|refuted|fact-checked)\s+by\s+(?:snopes|reuters|politifact|ap\s*news|factcheck|community\s*note)|"
    r"\b(out\s*of\s*context|old\s*(video|pic|photo|news)|recycled|from\s*20\d\d)\b",
    re.IGNORECASE,
)

FACT_CHECKER_REGEX = re.compile(
    r"\b(snopes|factcheck|fact-check|politifact|community\s*note|lead\s*stories|full\s*fact|altnews|pibfactcheck)\b",
    re.IGNORECASE,
)

# Negations that might precede debunk words (e.g. "not fake", "isn't a hoax")
NEGATION_DEBUNK_REGEX = re.compile(
    r"\b(not|isn't|is\s+not|wasn't|was\s+not|aren't|are\s+not|ain't|no)\s+(fake|a\s+hoax|a\s+scam|a\s+lie|false)\b",
    re.IGNORECASE,
)

# Support / confirmation patterns in comments
SUPPORT_REGEX = re.compile(
    r"\b(verified|confirmed|true|legit|factually\s*correct|real\s*deal|accurate|"
    r"official\s*source|backed\s*by|credible|proven\s*true)\b",
    re.IGNORECASE,
)


class CommentAnalyzer:
    """Module 1: Analyzes comment sentiment cohesion, duplicate spam, emoji manipulation,
    temporal bursts, and crowdsourced fact-checking signals to produce a calibrated Comment Score (0-100).
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        zscore_threshold: float = 3.0,
    ):
        self.similarity_threshold = similarity_threshold
        self.zscore_threshold = zscore_threshold

    def evaluate_comment_fact_checking(self, comments: list[Comment]) -> dict[str, Any]:
        """Analyze comment text for crowdsourced fact-checking, skepticism, and debunking signals."""
        debunking_comments: list[str] = []
        supporting_comments: list[str] = []
        extracted_claims: list[str] = []
        has_fact_checker_reference = False

        for c in comments:
            txt = (c.text or "").strip()
            if not txt:
                continue

            # Check for negation of debunking ("not fake")
            is_negated = bool(NEGATION_DEBUNK_REGEX.search(txt))
            is_debunking = bool(DEBUNK_REGEX.search(txt)) and not is_negated
            is_supporting = bool(SUPPORT_REGEX.search(txt)) and not is_debunking

            if is_debunking:
                debunking_comments.append(txt)
                if any(k in txt.lower() for k in ["snopes", "factcheck", "fact-check", "reuters", "politifact", "community note"]):
                    has_fact_checker_reference = True
                # Extract potential debunking claim/context
                cleaned_claim = re.sub(r"https?://\S+", "", txt).strip()
                if len(cleaned_claim.split()) >= 3:
                    extracted_claims.append(cleaned_claim[:120])
            elif is_supporting:
                supporting_comments.append(txt)

        total = len(comments)
        debunk_count = len(debunking_comments)
        support_count = len(supporting_comments)
        debunk_ratio = round(debunk_count / total, 3) if total > 0 else 0.0
        support_ratio = round(support_count / total, 3) if total > 0 else 0.0

        # Determine comment fact check verdict
        if debunk_ratio >= 0.25 or (total <= 3 and debunk_count >= 1):
            verdict = "DEBUNKED_BY_COMMUNITY"
            summary = f"Strong community debunking detected: {debunk_count} of {total} comments refute this claim as false, fake, or a hoax."
        elif debunk_count > 0:
            verdict = "CONTESTED_BY_COMMENTS"
            summary = f"Community skepticism detected: {debunk_count} of {total} comments question or contest the credibility of this post."
        elif support_ratio >= 0.40:
            verdict = "SUPPORTED_BY_COMMENTS"
            summary = f"Comments generally confirm or corroborate this post ({support_count} of {total} supportive)."
        else:
            verdict = "ORGANIC_DISCUSSION"
            summary = f"Comments represent standard discussion ({total} comments analyzed)."

        return {
            "verdict": verdict,
            "debunk_ratio": debunk_ratio,
            "support_ratio": support_ratio,
            "debunk_count": debunk_count,
            "support_count": support_count,
            "has_fact_checker_reference": has_fact_checker_reference,
            "debunking_comments": debunking_comments[:5],
            "extracted_comment_claims": extracted_claims[:3],
            "summary": summary,
        }

    def analyze(self, comments: list[Comment]) -> dict[str, Any]:
        """Execute full Comment Analysis pipeline."""
        flags: list[str] = []
        n_comments = len(comments)

        # ----------------------------------------------------------------------
        # Edge Case 1: Empty comments
        # ----------------------------------------------------------------------
        if n_comments == 0:
            return {
                "comment_score": 50.0,  # Neutral baseline when no comments exist
                "metrics": {
                    "comment_count": 0,
                    "duplicate_ratio": 0.0,
                    "exact_duplicate_ratio": 0.0,
                    "near_duplicate_ratio": 0.0,
                    "average_similarity": 0.0,
                    "emoji_ratio": 0.0,
                    "emoji_entropy": 0.0,
                    "temporal_anomaly_score": 0.0,
                    "average_comments_per_minute": 0.0,
                    "debunk_ratio": 0.0,
                    "support_ratio": 0.0,
                },
                "fact_check": {
                    "verdict": "NO_COMMENTS",
                    "debunk_ratio": 0.0,
                    "support_ratio": 0.0,
                    "debunk_count": 0,
                    "support_count": 0,
                    "has_fact_checker_reference": False,
                    "debunking_comments": [],
                    "extracted_comment_claims": [],
                    "summary": "No comments available to evaluate crowdsourced fact-checking or discussion signals.",
                },
                "flags": ["NO_COMMENTS_AVAILABLE"],
            }

        # ----------------------------------------------------------------------
        # Step 1: Preprocessing & Text Normalization
        # ----------------------------------------------------------------------
        raw_texts = [c.text for c in comments if c.text]
        timestamps = [c.timestamp for c in comments if c.timestamp is not None]

        cleaned_texts_embedding = [clean_text_for_embedding(t) for t in raw_texts]
        valid_embedding_texts = [t for t in cleaned_texts_embedding if t]

        exact_norm_texts = [normalize_text_for_exact_match(t) for t in raw_texts]
        valid_exact_texts = [t for t in exact_norm_texts if t]

        # ----------------------------------------------------------------------
        # Step 2: Exact Duplicate Detection
        # ----------------------------------------------------------------------
        exact_duplicate_ratio = 0.0
        if len(valid_exact_texts) > 1:
            unique_count = len(set(valid_exact_texts))
            exact_duplicate_ratio = round((len(valid_exact_texts) - unique_count) / len(valid_exact_texts), 4)

        # ----------------------------------------------------------------------
        # Step 3: Semantic Similarity & Near-Duplicate Analysis (S-BERT)
        # ----------------------------------------------------------------------
        if len(valid_embedding_texts) <= 1:
            similarity_metrics = {
                "average_similarity": 0.0,
                "max_similarity": 0.0,
                "near_duplicate_ratio": 0.0,
                "near_duplicate_comment_ratio": 0.0,
            }
        else:
            try:
                similarity_metrics = compute_semantic_similarity_features(
                    cleaned_texts=valid_embedding_texts,
                    similarity_threshold=self.similarity_threshold,
                )
            except Exception as exc:
                logger.warning("Error during S-BERT similarity calculation: %s", exc)
                similarity_metrics = {
                    "average_similarity": 0.0,
                    "max_similarity": 0.0,
                    "near_duplicate_ratio": 0.0,
                    "near_duplicate_comment_ratio": 0.0,
                }
                flags.append("SIMILARITY_CALCULATION_FALLBACK")

        duplicate_ratio = max(
            exact_duplicate_ratio,
            similarity_metrics["near_duplicate_comment_ratio"],
        )

        # ----------------------------------------------------------------------
        # Step 4: Emoji Analysis
        # ----------------------------------------------------------------------
        emoji_metrics = compute_emoji_features(raw_texts)

        # ----------------------------------------------------------------------
        # Step 5: Temporal & Anomaly Analysis
        # ----------------------------------------------------------------------
        temporal_metrics = compute_temporal_features(
            timestamps=timestamps,
            zscore_threshold=self.zscore_threshold,
        )

        # ----------------------------------------------------------------------
        # Step 6: Comment Fact-Checking & Crowdsourced Stance Analysis
        # ----------------------------------------------------------------------
        fact_check_eval = self.evaluate_comment_fact_checking(comments)
        if fact_check_eval["verdict"] == "DEBUNKED_BY_COMMUNITY":
            flags.append("COMMENTS_DEBUNK_CLAIM")
        elif fact_check_eval["verdict"] == "CONTESTED_BY_COMMENTS":
            flags.append("COMMENTS_CONTEST_CLAIM")
        elif fact_check_eval["verdict"] == "SUPPORTED_BY_COMMENTS":
            flags.append("COMMENTS_VERIFY_CLAIM")

        if fact_check_eval["has_fact_checker_reference"]:
            flags.append("FACT_CHECK_CITED_IN_COMMENTS")

        # ----------------------------------------------------------------------
        # Step 7: Flag Generation
        # ----------------------------------------------------------------------
        if duplicate_ratio >= 0.40:
            flags.append("HIGH_DUPLICATE_COMMENT_RATIO")
        elif duplicate_ratio >= 0.20:
            flags.append("MODERATE_DUPLICATE_COMMENT_RATIO")

        if similarity_metrics["average_similarity"] >= 0.70 and len(valid_embedding_texts) >= 4:
            flags.append("SUSPICIOUS_SEMANTIC_COORDINATION")

        if emoji_metrics["excessive_emoji_ratio"] >= 0.35:
            flags.append("EXCESSIVE_EMOJI_SPAM")

        if temporal_metrics["zscore_burst_detected"] == 1.0 or temporal_metrics["iqr_burst_detected"] == 1.0:
            flags.append("TEMPORAL_BURST_ACTIVITY_DETECTED")

        if n_comments == 1:
            flags.append("SINGLE_COMMENT_ONLY")

        # ----------------------------------------------------------------------
        # Step 8: Calibrated Comment Score Computation (0 - 100)
        # ----------------------------------------------------------------------
        if n_comments == 1:
            if fact_check_eval["verdict"] == "DEBUNKED_BY_COMMUNITY":
                comment_score = 25.0
            elif fact_check_eval["verdict"] == "SUPPORTED_BY_COMMENTS":
                comment_score = 80.0
            else:
                comment_score = 65.0
        else:
            score = 100.0

            # Penalty 1: Duplicate / Copypasta Penalty (up to 40 points)
            score -= duplicate_ratio * 40.0

            # Penalty 2: Bot coordination semantic similarity (up to 20 points)
            if similarity_metrics["average_similarity"] > 0.55:
                sim_excess = (similarity_metrics["average_similarity"] - 0.55) / 0.45
                score -= sim_excess * 20.0

            # Penalty 3: Temporal burst (up to 25 points)
            score -= temporal_metrics["temporal_anomaly_score"] * 25.0

            # Penalty 4: Excessive emoji spam (up to 15 points)
            score -= emoji_metrics["excessive_emoji_ratio"] * 15.0

            # Penalty 5 / Reward: Comment Fact Check Stance
            if fact_check_eval["debunk_ratio"] > 0:
                debunk_penalty = min(70.0, fact_check_eval["debunk_ratio"] * 85.0)
                score -= debunk_penalty
                if fact_check_eval["verdict"] == "DEBUNKED_BY_COMMUNITY":
                    score = min(score, 35.0)
                elif fact_check_eval["verdict"] == "CONTESTED_BY_COMMENTS":
                    score = min(score, 55.0)
            elif fact_check_eval["support_ratio"] >= 0.40:
                score = min(100.0, score + 10.0)

            comment_score = round(max(0.0, min(100.0, score)), 2)

        metrics_summary = {
            "comment_count": n_comments,
            "duplicate_ratio": duplicate_ratio,
            "exact_duplicate_ratio": exact_duplicate_ratio,
            "near_duplicate_ratio": similarity_metrics["near_duplicate_ratio"],
            "average_similarity": similarity_metrics["average_similarity"],
            "emoji_ratio": emoji_metrics["emoji_comment_ratio"],
            "emoji_entropy": emoji_metrics["emoji_entropy"],
            "excessive_emoji_ratio": emoji_metrics["excessive_emoji_ratio"],
            "temporal_anomaly_score": temporal_metrics["temporal_anomaly_score"],
            "average_comments_per_minute": temporal_metrics["average_comments_per_minute"],
            "max_comments_per_minute": temporal_metrics["max_comments_per_minute"],
            "zscore_max": temporal_metrics["zscore_max"],
            "debunk_ratio": fact_check_eval["debunk_ratio"],
            "support_ratio": fact_check_eval["support_ratio"],
        }

        return {
            "comment_score": comment_score,
            "metrics": metrics_summary,
            "fact_check": fact_check_eval,
            "flags": flags,
        }


comment_analyzer = CommentAnalyzer()

