"""Module 1: Comment Analysis Engine implementation."""

from collections import Counter
from datetime import datetime
import re
from typing import Any

from app.modules.comment_analysis.preprocessing import (
    clean_text_for_embedding,
    compute_emoji_features,
    normalize_text_for_exact_match,
)
from app.modules.comment_analysis.similarity import (
    compute_semantic_clusters,
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
    r"cgi|deepfake|ai\s*generated|ai-generated|photoshop(ped)?|clickbait|phishing|manipulated)\b|"
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
    """Module 1: Comment Analysis Engine.

    Evaluates comment sentiment cohesion, duplicate spam, semantic clusters,
    emoji entropy/distribution, temporal bursts (Z-score & IQR), and crowdsourced
    debunking/skepticism signals to produce a calibrated Comment Score (0-100).
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        zscore_threshold: float = 3.0,
    ):
        self.similarity_threshold = similarity_threshold
        self.zscore_threshold = zscore_threshold

    @staticmethod
    def _sanitize_comment_item(item: Any) -> tuple[dict[str, Any] | None, bool]:
        """Extract text and timestamp safely from any comment input format.

        Supports Comment instances, dicts, strings, and handles malformed data.
        Returns (sanitized_dict, is_malformed).
        """
        if item is None:
            return None, True

        is_malformed = False
        text: str = ""
        timestamp: datetime | None = None

        if isinstance(item, Comment):
            raw_text = item.text
            timestamp = item.timestamp
            text = str(raw_text).strip() if raw_text is not None else ""
        elif isinstance(item, dict):
            raw_text = item.get("text")
            raw_ts = item.get("timestamp")
            if raw_text is not None:
                text = str(raw_text).strip()
            else:
                is_malformed = True

            if isinstance(raw_ts, datetime):
                timestamp = raw_ts
            elif isinstance(raw_ts, str):
                try:
                    timestamp = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except Exception:
                    is_malformed = True
                    timestamp = None
            elif raw_ts is not None:
                is_malformed = True
        elif isinstance(item, str):
            text = item.strip()
        else:
            is_malformed = True
            try:
                text = str(item).strip()
            except Exception:
                text = ""

        if not text:
            return None, True

        return {"text": text, "timestamp": timestamp}, is_malformed

    def evaluate_comment_fact_checking(self, comments: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze comment text for crowdsourced fact-checking, skepticism, and debunking signals."""
        debunking_comments: list[str] = []
        supporting_comments: list[str] = []
        extracted_claims: list[str] = []
        has_fact_checker_reference = False

        for c in comments:
            txt = (c.get("text") or "").strip()
            if not txt:
                continue

            # Check for negation of debunking (e.g. "not fake")
            is_negated = bool(NEGATION_DEBUNK_REGEX.search(txt))
            is_debunking = bool(DEBUNK_REGEX.search(txt)) and not is_negated
            is_supporting = bool(SUPPORT_REGEX.search(txt)) and not is_debunking

            if is_debunking:
                debunking_comments.append(txt)
                if any(
                    k in txt.lower()
                    for k in [
                        "snopes",
                        "factcheck",
                        "fact-check",
                        "reuters",
                        "politifact",
                        "community note",
                        "ap news",
                    ]
                ):
                    has_fact_checker_reference = True
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

        if debunk_ratio >= 0.25 or (total <= 3 and debunk_count >= 1):
            verdict = "DEBUNKED_BY_COMMUNITY"
            summary = (
                f"Strong community debunking detected: {debunk_count} of {total} comments "
                f"refute this claim as false, fake, or a hoax."
            )
        elif debunk_count > 0:
            verdict = "CONTESTED_BY_COMMENTS"
            summary = (
                f"Community skepticism detected: {debunk_count} of {total} comments question "
                f"or contest the credibility of this post."
            )
        elif support_ratio >= 0.35:
            verdict = "SUPPORTED_BY_COMMENTS"
            summary = (
                f"Comments generally confirm or corroborate this post ({support_count} of {total} supportive)."
            )
        else:
            verdict = "ORGANIC_DISCUSSION"
            summary = f"Comments represent standard organic discussion ({total} comments analyzed)."

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

    def analyze(self, comments: Any) -> dict[str, Any]:
        """Execute full Comment Analysis pipeline and return structured results."""
        flags: list[str] = []

        # ----------------------------------------------------------------------
        # Step 0: Input Sanitization (Handle malformed comment data)
        # ----------------------------------------------------------------------
        if not isinstance(comments, list):
            comments = []

        sanitized_comments: list[dict[str, Any]] = []
        has_malformed = False

        for raw_item in comments:
            item_data, is_bad = self._sanitize_comment_item(raw_item)
            if is_bad:
                has_malformed = True
            if item_data is not None:
                sanitized_comments.append(item_data)

        if has_malformed:
            flags.append("MALFORMED_COMMENT_DATA")

        n_comments = len(sanitized_comments)

        # ----------------------------------------------------------------------
        # Edge Case 1: Empty comments
        # ----------------------------------------------------------------------
        if n_comments == 0:
            empty_cluster_info = {
                "num_clusters": 0,
                "total_clusters": 0,
                "coordinated_cluster_count": 0,
                "largest_cluster_size": 0,
                "largest_cluster_ratio": 0.0,
                "clusters": [],
            }
            empty_iqr_info = {
                "q25": 0.0,
                "q75": 0.0,
                "iqr": 0.0,
                "upper_bound": 0.0,
                "outlier_count": 0,
                "iqr_burst_detected": False,
            }
            empty_fact_check = {
                "verdict": "NO_COMMENTS",
                "debunk_ratio": 0.0,
                "support_ratio": 0.0,
                "debunk_count": 0,
                "support_count": 0,
                "has_fact_checker_reference": False,
                "debunking_comments": [],
                "extracted_comment_claims": [],
                "summary": "No comments available to evaluate crowdsourced fact-checking or discussion signals.",
            }
            flags.append("NO_COMMENTS_AVAILABLE")
            explanation = "No comments available. Neutral baseline credibility score assigned."

            metrics_summary = {
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
            }

            return {
                "score": 50.0,
                "status": "NO_COMMENTS",
                "comment_count": 0,
                "duplicate_ratio": 0.0,
                "semantic_similarity": 0.0,
                "cluster_information": empty_cluster_info,
                "cluster_info": empty_cluster_info,
                "temporal_burst_score": 0.0,
                "z_score": 0.0,
                "iqr_anomaly_info": empty_iqr_info,
                "emoji_entropy": 0.0,
                "debunk_ratio": 0.0,
                "support_ratio": 0.0,
                "detected_flags": flags,
                "explanation": explanation,
                # Aliases for backward compatibility
                "comment_score": 50.0,
                "metrics": metrics_summary,
                "fact_check": empty_fact_check,
                "flags": flags,
            }

        # ----------------------------------------------------------------------
        # Step 1: Text Preprocessing & Normalization
        # ----------------------------------------------------------------------
        raw_texts = [c["text"] for c in sanitized_comments]
        timestamps = [c["timestamp"] for c in sanitized_comments if c["timestamp"] is not None]

        cleaned_texts_embedding = [clean_text_for_embedding(t) for t in raw_texts]
        valid_embedding_texts = [t for t in cleaned_texts_embedding if t]

        exact_norm_texts = [normalize_text_for_exact_match(t) for t in raw_texts]
        valid_exact_texts = [t for t in exact_norm_texts if t]

        # ----------------------------------------------------------------------
        # Step 2: Exact Duplicate Detection
        # ----------------------------------------------------------------------
        exact_duplicate_ratio = 0.0
        exact_counts = Counter(valid_exact_texts)
        if len(valid_exact_texts) > 1:
            duplicate_instances = sum(cnt - 1 for cnt in exact_counts.values() if cnt > 1)
            exact_duplicate_ratio = round(duplicate_instances / len(valid_exact_texts), 4)

        # ----------------------------------------------------------------------
        # Step 3: Sentence-BERT Semantic Similarity & Clustering
        # ----------------------------------------------------------------------
        if len(valid_embedding_texts) <= 1:
            similarity_metrics = {
                "average_similarity": 0.0,
                "max_similarity": 0.0,
                "near_duplicate_ratio": 0.0,
                "near_duplicate_comment_ratio": 0.0,
            }
            cluster_info = {
                "num_clusters": len(valid_embedding_texts),
                "total_clusters": len(valid_embedding_texts),
                "coordinated_cluster_count": 0,
                "largest_cluster_size": len(valid_embedding_texts),
                "largest_cluster_ratio": 1.0 if valid_embedding_texts else 0.0,
                "clusters": (
                    [
                        {
                            "cluster_id": 0,
                            "size": 1,
                            "sample_text": valid_embedding_texts[0][:150],
                            "comment_indices": [0],
                            "cohesion": 1.0,
                        }
                    ]
                    if valid_embedding_texts
                    else []
                ),
            }
        else:
            try:
                similarity_metrics = compute_semantic_similarity_features(
                    cleaned_texts=valid_embedding_texts,
                    similarity_threshold=self.similarity_threshold,
                )
                cluster_info = compute_semantic_clusters(
                    cleaned_texts=valid_embedding_texts,
                    similarity_threshold=0.80,
                )
            except Exception as exc:
                logger.warning("Error during S-BERT similarity or clustering: %s", exc)
                similarity_metrics = {
                    "average_similarity": 0.0,
                    "max_similarity": 0.0,
                    "near_duplicate_ratio": 0.0,
                    "near_duplicate_comment_ratio": 0.0,
                }
                cluster_info = {
                    "num_clusters": len(valid_embedding_texts),
                    "total_clusters": len(valid_embedding_texts),
                    "coordinated_cluster_count": 0,
                    "largest_cluster_size": 1,
                    "largest_cluster_ratio": round(1.0 / len(valid_embedding_texts), 4),
                    "clusters": [],
                }
                flags.append("SIMILARITY_CALCULATION_FALLBACK")

        duplicate_ratio = max(
            exact_duplicate_ratio,
            similarity_metrics["near_duplicate_comment_ratio"],
        )

        # ----------------------------------------------------------------------
        # Step 4: Emoji Distribution & Shannon Entropy Analysis
        # ----------------------------------------------------------------------
        emoji_metrics = compute_emoji_features(raw_texts)

        # ----------------------------------------------------------------------
        # Step 5: Temporal Arrival Dynamics (Z-Score & IQR Outliers)
        # ----------------------------------------------------------------------
        temporal_metrics = compute_temporal_features(
            timestamps=timestamps,
            zscore_threshold=self.zscore_threshold,
        )

        # ----------------------------------------------------------------------
        # Step 6: Crowdsourced Fact-Checking & Skepticism Detection
        # ----------------------------------------------------------------------
        fact_check_eval = self.evaluate_comment_fact_checking(sanitized_comments)
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

        if (
            temporal_metrics.get("zscore_burst_detected") == 1.0
            or temporal_metrics.get("iqr_burst_detected") == 1.0
        ):
            flags.append("TEMPORAL_BURST_ACTIVITY_DETECTED")

        if n_comments == 1:
            flags.append("SINGLE_COMMENT_ONLY")

        # ----------------------------------------------------------------------
        # Step 8: Calibrated Score & Status Computation (0 - 100)
        # CRITICAL: Do not classify a post as fake solely because comments are anomalous.
        # Anomalous comments indicate spam/bot coordination, which degrades discussion
        # health, but does not prove the post itself is fake unless debunking exists.
        # ----------------------------------------------------------------------
        status = "ORGANIC"

        if n_comments == 1:
            status = "SINGLE_COMMENT"
            if fact_check_eval["verdict"] == "DEBUNKED_BY_COMMUNITY":
                comment_score = 30.0
                status = "DEBUNKED"
            elif fact_check_eval["verdict"] == "SUPPORTED_BY_COMMENTS":
                comment_score = 80.0
                status = "SUPPORTED"
            else:
                comment_score = 65.0
        else:
            # Baseline for healthy discussion
            base_score = 85.0

            # 1. Deductions for spam / copypasta (up to 25 pts)
            base_score -= duplicate_ratio * 25.0

            # 2. Deductions for semantic coordination (up to 15 pts)
            if similarity_metrics["average_similarity"] > 0.65:
                sim_excess = (similarity_metrics["average_similarity"] - 0.65) / 0.35
                base_score -= min(15.0, sim_excess * 15.0)

            # 3. Deductions for cluster concentration (up to 10 pts)
            if (
                cluster_info.get("largest_cluster_ratio", 0.0) >= 0.50
                and cluster_info.get("largest_cluster_size", 0) >= 3
            ):
                base_score -= 8.0

            # 4. Deductions for temporal burst (up to 15 pts)
            base_score -= temporal_metrics.get("temporal_burst_score", 0.0) * 15.0

            # 5. Deductions for emoji spam (up to 10 pts)
            base_score -= emoji_metrics["excessive_emoji_ratio"] * 10.0

            # 6. Fact-checking stance impact
            if fact_check_eval["debunk_ratio"] > 0:
                debunk_penalty = min(60.0, fact_check_eval["debunk_ratio"] * 75.0)
                base_score -= debunk_penalty
                if fact_check_eval["verdict"] == "DEBUNKED_BY_COMMUNITY":
                    base_score = min(base_score, 35.0)
                    status = "DEBUNKED"
                elif fact_check_eval["verdict"] == "CONTESTED_BY_COMMENTS":
                    base_score = min(base_score, 55.0)
                    status = "CONTESTED"
            elif fact_check_eval["support_ratio"] >= 0.35:
                base_score = min(95.0, base_score + 10.0)
                status = "SUPPORTED"
            elif duplicate_ratio >= 0.40 or cluster_info.get("largest_cluster_ratio", 0.0) >= 0.60:
                status = "SPAM_DETECTED"
            elif temporal_metrics.get("zscore_burst_detected") == 1.0:
                status = "BURST_DETECTED"
            else:
                status = "ORGANIC"

            # CRITICAL RULE: Do not classify as fake (< 40.0) solely because comments are anomalous
            if fact_check_eval["debunk_ratio"] == 0.0:
                base_score = max(40.0, base_score)

            comment_score = round(max(10.0, min(100.0, base_score)), 2)

        # ----------------------------------------------------------------------
        # Step 9: Detailed Evidence Explanation Generation
        # ----------------------------------------------------------------------
        explanation_parts = []
        explanation_parts.append(
            f"Analyzed {n_comments} comment{'s' if n_comments != 1 else ''} with status [{status}]."
        )

        if fact_check_eval["verdict"] == "DEBUNKED_BY_COMMUNITY":
            explanation_parts.append(
                f"Community debunking detected: {fact_check_eval['debunk_count']} comments refute the claim."
            )
            if fact_check_eval["has_fact_checker_reference"]:
                explanation_parts.append("Reputable fact-checking sources were cited in comments.")
        elif fact_check_eval["verdict"] == "CONTESTED_BY_COMMENTS":
            explanation_parts.append(
                f"Community skepticism detected: {fact_check_eval['debunk_count']} comments question veracity."
            )
        elif fact_check_eval["verdict"] == "SUPPORTED_BY_COMMENTS":
            explanation_parts.append(
                f"Community support detected: {fact_check_eval['support_count']} comments corroborate the post."
            )

        if duplicate_ratio >= 0.30:
            explanation_parts.append(
                f"High duplicate ratio ({duplicate_ratio * 100:.1f}%) suggests automated or copypasta activity."
            )
        elif cluster_info.get("coordinated_cluster_count", 0) > 0:
            explanation_parts.append(
                f"Identified {cluster_info['num_clusters']} semantic clusters with "
                f"{cluster_info['coordinated_cluster_count']} coordinated groups."
            )

        if temporal_metrics.get("zscore_burst_detected") == 1.0:
            explanation_parts.append(
                f"Temporal arrival surge detected (Z-score: {temporal_metrics.get('z_score')})."
            )

        if emoji_metrics.get("excessive_emoji_ratio", 0.0) >= 0.25:
            explanation_parts.append(
                f"Excessive emoji usage detected ({emoji_metrics['excessive_emoji_ratio'] * 100:.1f}% comments)."
            )

        explanation = " ".join(explanation_parts)

        # ----------------------------------------------------------------------
        # Step 10: Structured Return Package
        # ----------------------------------------------------------------------
        metrics_summary = {
            "comment_count": n_comments,
            "duplicate_ratio": duplicate_ratio,
            "exact_duplicate_ratio": exact_duplicate_ratio,
            "near_duplicate_ratio": similarity_metrics["near_duplicate_ratio"],
            "average_similarity": similarity_metrics["average_similarity"],
            "cluster_count": cluster_info["num_clusters"],
            "largest_cluster_size": cluster_info["largest_cluster_size"],
            "emoji_ratio": emoji_metrics["emoji_comment_ratio"],
            "emoji_entropy": emoji_metrics["emoji_entropy"],
            "excessive_emoji_ratio": emoji_metrics["excessive_emoji_ratio"],
            "temporal_anomaly_score": temporal_metrics.get("temporal_anomaly_score", 0.0),
            "temporal_burst_score": temporal_metrics.get("temporal_burst_score", 0.0),
            "average_comments_per_minute": temporal_metrics.get("average_comments_per_minute", 0.0),
            "max_comments_per_minute": temporal_metrics.get("max_comments_per_minute", 0.0),
            "zscore_max": temporal_metrics.get("zscore_max", 0.0),
            "z_score": temporal_metrics.get("z_score", 0.0),
            "debunk_ratio": fact_check_eval["debunk_ratio"],
            "support_ratio": fact_check_eval["support_ratio"],
        }

        return {
            "score": comment_score,
            "status": status,
            "comment_count": n_comments,
            "duplicate_ratio": duplicate_ratio,
            "semantic_similarity": similarity_metrics["average_similarity"],
            "cluster_information": cluster_info,
            "cluster_info": cluster_info,
            "temporal_burst_score": temporal_metrics.get("temporal_burst_score", 0.0),
            "z_score": temporal_metrics.get("z_score", 0.0),
            "iqr_anomaly_info": temporal_metrics.get("iqr_anomaly_info", {}),
            "emoji_entropy": emoji_metrics["emoji_entropy"],
            "debunk_ratio": fact_check_eval["debunk_ratio"],
            "support_ratio": fact_check_eval["support_ratio"],
            "detected_flags": flags,
            "explanation": explanation,
            # Backward-compatible fields
            "comment_score": comment_score,
            "metrics": metrics_summary,
            "fact_check": fact_check_eval,
            "flags": flags,
        }


comment_analyzer = CommentAnalyzer()
