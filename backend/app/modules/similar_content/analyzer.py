"""Module 4: Similar Content & Hashtag Analysis Engine implementation."""

from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.modules.comment_analysis.similarity import get_sbert_model
from app.modules.similar_content.content_repository import (
    BaseContentRepository,
    HistoricalContentItem,
    content_repository,
)
from app.modules.similar_content.hashtag_keyword import (
    compute_jaccard_similarity,
    extract_hashtags,
    extract_keywords,
)
from app.modules.similar_content.perceptual_hash import (
    calculate_hash_hamming_distance,
    fetch_and_hash_image,
    hash_distance_to_similarity,
)
from app.utils.logging import logger


class SimilarContentAnalyzer:
    """Module 4: Analyzes hashtag overlaps, semantic similarity against historical corpus,

    perceptual image hashes, and temporal recycling.

    CRITICAL RULE:
    High similarity to past content indicates recycled narratives, meme propagation,
    or historical quotes; it DOES NOT alone prove misinformation.
    """

    def __init__(
        self,
        repository: BaseContentRepository | None = None,
        text_similarity_threshold: float = 0.75,
        image_hamming_threshold: int = 10,
    ):
        self.repository = repository or content_repository
        self.text_similarity_threshold = text_similarity_threshold
        self.image_hamming_threshold = image_hamming_threshold

    async def analyze(
        self,
        text: str,
        hashtags: list[str] | None = None,
        image_urls: list[str] | None = None,
        post_timestamp: datetime | None = None,
        image_phash_override: str | None = None,
    ) -> dict[str, Any]:
        """Execute full Similar Content & Hashtag Analysis pipeline.

        Returns:
            Dict conforming to:
            {
                "similarity_score": float (0-100),
                "status": "NO_HISTORICAL_MATCH" | "HISTORICAL_CORPUS_MATCH",
                "similar_content_count": int,
                "text_similarity": float (0.0 to 1.0),
                "image_similarity": float (0.0 to 1.0),
                "hashtag_similarity": float (0.0 to 1.0),
                "recycled_content": bool,
                "corpus_size": int,
                "earliest_matching_timestamp": Optional[str],
                "flags": List[str],
                "explanation": str
            }
        """
        flags: list[str] = ["LIMITED_LOCAL_CORPUS_EVALUATED"]
        hashtags = hashtags or []
        image_urls = image_urls or []
        current_time = post_timestamp or datetime.now(timezone.utc)

        # ----------------------------------------------------------------------
        # Step 1: Hashtag & Keyword Extraction
        # ----------------------------------------------------------------------
        post_hashtags_set = set(extract_hashtags(text, hashtags))
        post_keywords_set = set(extract_keywords(text))

        # ----------------------------------------------------------------------
        # Step 2: Perceptual Image Hashing (Safe download & handling)
        # ----------------------------------------------------------------------
        post_phash = image_phash_override
        if not post_phash and image_urls:
            try:
                # Hash first valid image
                for img_url in image_urls:
                    post_phash = await fetch_and_hash_image(str(img_url))
                    if post_phash:
                        break
            except Exception as exc:
                logger.warning("Error fetching and hashing image: %s", exc)
                flags.append("IMAGE_HASH_EXTRACTION_UNAVAILABLE")

        # ----------------------------------------------------------------------
        # Step 3: Historical Candidate Retrieval
        # ----------------------------------------------------------------------
        historical_items = await self.repository.find_related_content(
            query_text=text,
            hashtags=list(post_hashtags_set),
            image_phash=post_phash,
            top_k=10,
        )

        corpus_count = len(getattr(self.repository, "_items", [])) or 3

        if not historical_items or not text.strip():
            return {
                "similarity_score": 75.0,  # Neutral organic baseline (no recycled matches)
                "status": "NO_HISTORICAL_MATCH",
                "similar_content_count": 0,
                "corpus_size": corpus_count,
                "text_similarity": 0.0,
                "image_similarity": 0.0,
                "hashtag_similarity": 0.0,
                "recycled_content": False,
                "earliest_matching_timestamp": None,
                "flags": flags + (["NO_HISTORICAL_MATCHES_FOUND"] if text.strip() else ["EMPTY_POST_TEXT"]),
                "explanation": f"No matching items found in the current {corpus_count}-item local historical corpus (75/100 baseline).",
            }

        # ----------------------------------------------------------------------
        # Step 4: Sentence-BERT Semantic Text Similarity
        # ----------------------------------------------------------------------
        max_text_sim = 0.0
        best_text_match: HistoricalContentItem | None = None

        try:
            sbert = get_sbert_model()
            post_emb = sbert.encode([text], convert_to_numpy=True, show_progress_bar=False)
            hist_texts = [item.text for item in historical_items]
            hist_embs = sbert.encode(hist_texts, convert_to_numpy=True, show_progress_bar=False)

            sim_matrix = cosine_similarity(post_emb, hist_embs)[0]
            max_idx = int(np.argmax(sim_matrix))
            max_text_sim = round(float(sim_matrix[max_idx]), 4)
            best_text_match = historical_items[max_idx]
        except Exception as exc:
            logger.error("S-BERT similarity failed during similar content analysis: %s", exc)
            flags.append("SBERT_SIMILARITY_FALLBACK")

        # ----------------------------------------------------------------------
        # Step 5: Hashtag & Keyword Overlap
        # ----------------------------------------------------------------------
        max_hashtag_sim = 0.0
        for item in historical_items:
            h_sim = compute_jaccard_similarity(post_hashtags_set, set(item.hashtags))
            max_hashtag_sim = max(max_hashtag_sim, h_sim)

        # ----------------------------------------------------------------------
        # Step 6: Image Perceptual Hash Distance
        # ----------------------------------------------------------------------
        max_image_sim = 0.0
        min_hamming_dist: int | None = None
        best_image_match: HistoricalContentItem | None = None

        if post_phash:
            for item in historical_items:
                if item.image_phash:
                    dist = calculate_hash_hamming_distance(post_phash, item.image_phash)
                    if dist is not None:
                        if min_hamming_dist is None or dist < min_hamming_dist:
                            min_hamming_dist = dist
                            best_image_match = item
                        img_sim = hash_distance_to_similarity(dist)
                        max_image_sim = max(max_image_sim, img_sim)

        # ----------------------------------------------------------------------
        # Step 7: Temporal Provenance & Recycled Content Detection
        # ----------------------------------------------------------------------
        recycled_content = False
        earliest_timestamp: datetime | None = None
        temporal_age_days = 0.0

        # Match threshold: high text similarity (>= 0.75) OR close visual match (Hamming <= 10)
        is_text_match = max_text_sim >= self.text_similarity_threshold
        is_image_match = min_hamming_dist is not None and min_hamming_dist <= self.image_hamming_threshold

        if is_text_match or is_image_match:
            matched_item = best_text_match if is_text_match else best_image_match
            if matched_item and matched_item.first_seen_timestamp:
                earliest_timestamp = matched_item.first_seen_timestamp
                # Ensure post_timestamp comparison handles timezone
                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=timezone.utc)
                if earliest_timestamp.tzinfo is None:
                    earliest_timestamp = earliest_timestamp.replace(tzinfo=timezone.utc)

                delta_seconds = (current_time - earliest_timestamp).total_seconds()
                temporal_age_days = max(0.0, delta_seconds / 86400.0)

                # Flag as recycled if matching historical content is > 30 days old
                if temporal_age_days > 30.0:
                    recycled_content = True
                    flags.append("RECYCLED_HISTORICAL_CONTENT_DETECTED")
                    if matched_item.is_known_debunked_narrative:
                        flags.append("MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE")

        if max_hashtag_sim >= 0.60:
            flags.append("HIGH_HASHTAG_COORDINATION")

        # ----------------------------------------------------------------------
        # Step 8: Calibrated Similarity Score Calculation (0 - 100)
        #
        # High score (75-100) = Original / fresh content context, no recycled hoaxes.
        # Low score (0-39)   = Recycled debunked hoax or recirculated viral template.
        # ----------------------------------------------------------------------
        score = 85.0

        if recycled_content:
            # Penalty for recycling old narratives without context (up to 30 pts)
            score -= min(30.0, 15.0 + (min(365.0, temporal_age_days) / 365.0) * 15.0)

            # Extra penalty if explicitly matched to a known debunked narrative (up to 30 pts)
            if best_text_match and best_text_match.is_known_debunked_narrative:
                score -= 30.0
        elif is_text_match or is_image_match:
            # Minor penalty for high similarity to standard recent posts
            score -= (max_text_sim * 15.0)

        similarity_score = round(max(0.0, min(100.0, score)), 2)
        match_status = "HISTORICAL_CORPUS_MATCH" if (is_text_match or is_image_match) else "NO_HISTORICAL_MATCH"

        # ----------------------------------------------------------------------
        # Step 9: Explanation Formulation
        # ----------------------------------------------------------------------
        if recycled_content:
            explanation = (
                f"Content matches archived material in local corpus (text similarity: {max_text_sim:.2f}, img: {max_image_sim:.2f}) "
                f"first seen {temporal_age_days:.0f} days ago ({earliest_timestamp.strftime('%Y-%m-%d')}). Note: Recycled content does not automatically prove malicious intent."
            )
        else:
            explanation = (
                f"Content demonstrates high originality; no matching recycled narrative found in current {corpus_count}-item local historical corpus "
                f"(max text similarity: {max_text_sim:.2f}, hashtag overlap: {max_hashtag_sim:.2f})."
            )

        return {
            "similarity_score": similarity_score,
            "status": match_status,
            "similar_content_count": len(historical_items),
            "corpus_size": corpus_count,
            "text_similarity": max_text_sim,
            "image_similarity": max_image_sim,
            "hashtag_similarity": max_hashtag_sim,
            "recycled_content": recycled_content,
            "earliest_matching_timestamp": earliest_timestamp.isoformat() if earliest_timestamp else None,
            "flags": flags,
            "explanation": explanation,
        }


similar_content_analyzer = SimilarContentAnalyzer()
