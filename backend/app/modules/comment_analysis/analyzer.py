"""Module 1: Comment Analysis Engine implementation."""

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


class CommentAnalyzer:
    """Module 1: Analyzes comment sentiment cohesion, duplicate spam, emoji manipulation,

    and temporal bursts to produce a calibrated Comment Score (0-100).

    IMPORTANT:
    Suspicious comment activity indicates inorganic discussion, astroturfing, or brigading;
    it does NOT definitively prove the underlying factual claim is fake.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        zscore_threshold: float = 3.0,
    ):
        self.similarity_threshold = similarity_threshold
        self.zscore_threshold = zscore_threshold

    def analyze(self, comments: list[Comment]) -> dict[str, Any]:
        """Execute full Comment Analysis pipeline.

        Pipeline:
        Comments -> Preprocessing -> S-BERT Semantic Similarity -> Exact / Near Duplicate Detection
                 -> Emoji Entropy & Distribution -> Temporal Burst Analysis -> Calibrated Scoring

        Returns:
            Dict conforming to:
            {
                "comment_score": float (0-100),
                "metrics": {
                    "comment_count": int,
                    "duplicate_ratio": float,
                    "average_similarity": float,
                    "emoji_ratio": float,
                    "temporal_anomaly_score": float,
                    ...
                },
                "flags": List[str]
            }
        """
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
                },
                "flags": ["NO_COMMENTS_AVAILABLE"],
            }

        # ----------------------------------------------------------------------
        # Step 1: Preprocessing & Text Normalization
        # ----------------------------------------------------------------------
        raw_texts = [c.text for c in comments if c.text]
        timestamps = [c.timestamp for c in comments if c.timestamp is not None]

        cleaned_texts_embedding = [clean_text_for_embedding(t) for t in raw_texts]
        # Filter out purely blank items after cleaning
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
        # Edge Case 2: 1 comment
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

        # Total combined duplicate ratio (maximum of exact and near duplicate)
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
        # Step 6: Flag Generation
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
        # Step 7: Calibrated Comment Score Computation (0 - 100)
        #
        # High Comment Score (80-100) = Healthy, diverse, organic discussion.
        # Low Comment Score (0-39)   = High repetition, bot farm templates, inorganic burst.
        # ----------------------------------------------------------------------
        if n_comments == 1:
            comment_score = 65.0  # Slightly above neutral for single organic comment
        else:
            # Baseline is 100 points
            score = 100.0

            # Penalty 1: Duplicate / Copypasta Penalty (up to 40 points deduction)
            # duplicate_ratio of 50% deducts 25 points, 100% deducts 40 points
            score -= duplicate_ratio * 40.0

            # Penalty 2: Overly high semantic similarity / bot coordination (up to 20 points)
            if similarity_metrics["average_similarity"] > 0.55:
                sim_excess = (similarity_metrics["average_similarity"] - 0.55) / 0.45
                score -= sim_excess * 20.0

            # Penalty 3: Temporal burst / brigading (up to 25 points)
            score -= temporal_metrics["temporal_anomaly_score"] * 25.0

            # Penalty 4: Excessive emoji spam (up to 15 points)
            score -= emoji_metrics["excessive_emoji_ratio"] * 15.0

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
        }

        return {
            "comment_score": comment_score,
            "metrics": metrics_summary,
            "flags": flags,
        }


comment_analyzer = CommentAnalyzer()
