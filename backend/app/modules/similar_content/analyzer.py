"""Module 4: Similar Content & Hashtag Analysis Engine implementation."""

from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.modules.comment_analysis.similarity import get_cached_embeddings, get_sbert_model
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
        image_dhash_override: str | None = None,
        image_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        """Execute full Similar Content & Hashtag Analysis pipeline.

        Returns:
            Dict conforming to:
            {
                "score": float (0-100),
                "recycled_content": bool,
                "visual_similarity": float (0.0 to 1.0),
                "semantic_similarity": float (0.0 to 1.0),
                "keyword_similarity": float (0.0 to 1.0),
                "matches": List[Dict],
                "flags": List[str],
                "explanation": str,
                # Compatibility fields:
                "similarity_score": float,
                "text_similarity": float,
                "image_similarity": float,
                "hashtag_similarity": float,
                "status": str,
                "similar_content_count": int,
                "corpus_size": int,
                "earliest_matching_timestamp": Optional[str],
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
        # Step 2: Perceptual Image Hashing (pHash + dHash)
        # ----------------------------------------------------------------------
        post_phash = image_phash_override
        post_dhash = image_dhash_override

        if image_bytes:
            from app.modules.similar_content.perceptual_hash import compute_image_hashes

            computed = compute_image_hashes(image_bytes)
            post_phash = computed.get("phash")
            post_dhash = computed.get("dhash")
        elif not post_phash and image_urls:
            try:
                from app.modules.similar_content.perceptual_hash import fetch_and_hash_image_full

                for img_url in image_urls:
                    hashes = await fetch_and_hash_image_full(str(img_url))
                    if hashes.get("phash") or hashes.get("dhash"):
                        post_phash = hashes.get("phash")
                        post_dhash = hashes.get("dhash")
                        break
            except Exception as exc:
                logger.warning("Error fetching and hashing image: %s", exc)
                flags.append("IMAGE_HASH_EXTRACTION_UNAVAILABLE")

        # ----------------------------------------------------------------------
        # Step 3: Historical Candidate Retrieval from In-Memory Corpus
        # ----------------------------------------------------------------------
        historical_items = await self.repository.find_related_content(
            query_text=text,
            hashtags=list(post_hashtags_set),
            image_phash=post_phash,
            image_dhash=post_dhash,
            top_k=10,
        )

        corpus_count = len(getattr(self.repository, "_items", [])) or len(historical_items) or 3

        if not text.strip() and not post_phash:
            return {
                "score": 75.0,
                "similarity_score": 75.0,
                "recycled_content": False,
                "visual_similarity": 0.0,
                "semantic_similarity": 0.0,
                "keyword_similarity": 0.0,
                "matches": [],
                "flags": flags + ["EMPTY_POST_TEXT"],
                "explanation": f"Empty post text analyzed against {corpus_count}-item local historical corpus (75/100 baseline).",
                "status": "NO_HISTORICAL_MATCH",
                "similar_content_count": 0,
                "corpus_size": corpus_count,
                "text_similarity": 0.0,
                "image_similarity": 0.0,
                "hashtag_similarity": 0.0,
                "earliest_matching_timestamp": None,
            }

        # ----------------------------------------------------------------------
        # Step 4: Sentence-BERT Semantic Text Similarity
        # ----------------------------------------------------------------------
        text_sims: list[float] = [0.0] * len(historical_items)

        if text.strip() and historical_items:
            try:
                sbert = get_sbert_model()
                post_emb = get_cached_embeddings([text], model=sbert)
                hist_texts = [item.text for item in historical_items]
                hist_embs = get_cached_embeddings(hist_texts, model=sbert)

                cos_sims = cosine_similarity(post_emb, hist_embs)[0]
                text_sims = [max(0.0, round(float(s), 4)) for s in cos_sims]
            except Exception as exc:
                logger.error("S-BERT similarity failed during similar content analysis: %s", exc)
                flags.append("SBERT_SIMILARITY_FALLBACK")
                for i, item in enumerate(historical_items):
                    text_sims[i] = compute_jaccard_similarity(post_keywords_set, set(item.keywords))

        # ----------------------------------------------------------------------
        # Step 5: Multi-Modal Item Matching & Provenance Evaluation
        # ----------------------------------------------------------------------
        from app.modules.similar_content.perceptual_hash import compare_visual_similarity

        matches: list[dict[str, Any]] = []
        max_visual_sim = 0.0
        max_semantic_sim = 0.0
        max_keyword_sim = 0.0
        best_overall_match: HistoricalContentItem | None = None
        recycled_content = False
        earliest_timestamp: datetime | None = None
        temporal_age_days = 0.0

        for idx, item in enumerate(historical_items):
            sem_sim = text_sims[idx] if idx < len(text_sims) else 0.0

            # Visual similarity using pHash + dHash
            vis_sim = 0.0
            if post_phash or post_dhash:
                vis_sim = compare_visual_similarity(
                    post_phash,
                    item.image_phash,
                    post_dhash,
                    getattr(item, "image_dhash", None),
                )

            # Keyword & Hashtag Jaccard similarity
            h_sim = compute_jaccard_similarity(post_hashtags_set, set(item.hashtags))
            k_sim = compute_jaccard_similarity(post_keywords_set, set(item.keywords))
            kw_sim = round(max(h_sim, k_sim), 4)

            max_visual_sim = max(max_visual_sim, vis_sim)
            max_semantic_sim = max(max_semantic_sim, sem_sim)
            max_keyword_sim = max(max_keyword_sim, kw_sim)

            # Item age calculation
            item_age_days = None
            if item.first_seen_timestamp:
                item_ts = item.first_seen_timestamp
                if current_time.tzinfo is None:
                    c_time = current_time.replace(tzinfo=timezone.utc)
                else:
                    c_time = current_time
                if item_ts.tzinfo is None:
                    i_time = item_ts.replace(tzinfo=timezone.utc)
                else:
                    i_time = item_ts
                item_age_days = max(0.0, (c_time - i_time).total_seconds() / 86400.0)

            # Check if this item constitutes a recycled match
            is_match = (sem_sim >= self.text_similarity_threshold) or (vis_sim >= 0.85)
            if is_match and item_age_days is not None and item_age_days > 30.0:
                recycled_content = True
                if best_overall_match is None or max(sem_sim, vis_sim) > max(
                    max_semantic_sim, max_visual_sim
                ):
                    best_overall_match = item
                    earliest_timestamp = item.first_seen_timestamp
                    temporal_age_days = item_age_days

            matches.append({
                "item_id": item.item_id,
                "text": item.text,
                "visual_similarity": round(vis_sim, 4),
                "semantic_similarity": round(sem_sim, 4),
                "keyword_similarity": round(kw_sim, 4),
                "historical_age_days": round(item_age_days, 1) if item_age_days is not None else None,
                "first_seen_timestamp": item.first_seen_timestamp.isoformat() if item.first_seen_timestamp else None,
                "is_known_debunked": item.is_known_debunked_narrative,
                "source_context": item.source_context,
            })

        # Sort matches by strongest similarity descending
        matches.sort(
            key=lambda m: max(m["semantic_similarity"], m["visual_similarity"], m["keyword_similarity"]),
            reverse=True,
        )

        if recycled_content:
            flags.append("RECYCLED_HISTORICAL_CONTENT_DETECTED")
            if best_overall_match and best_overall_match.is_known_debunked_narrative:
                flags.append("MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE")

        if max_keyword_sim >= 0.60:
            flags.append("HIGH_HASHTAG_COORDINATION")

        # ----------------------------------------------------------------------
        # Step 6: Calibrated Similarity Score Calculation (0 - 100)
        #
        # High score (75-100) = Original / fresh content context, no recycled hoaxes.
        # Moderate score (50-74) = Moderate similarity to past posts or sensational phrasing.
        # Low score (0-49)   = Recycled debunked hoax or viral duplicate template.
        # ----------------------------------------------------------------------
        import re
        score = 85.0

        is_sensational_viral = bool(
            re.search(
                r"\b(breaking|urgent|share to save lives|spread the word|secret cure|miracle cure|must share|watch before deleted|shocking)\b",
                text,
                re.I,
            )
            or (text.count("!") >= 3)
            or (len(post_hashtags_set) >= 5)
        )
        if is_sensational_viral:
            score -= 35.0
            flags.append("SENSATIONAL_VIRAL_FORMATTING")

        if recycled_content:
            # Penalty for recirculating old content without attribution (up to 30 pts)
            score -= min(30.0, 15.0 + (min(365.0, temporal_age_days) / 365.0) * 15.0)

            # Heavy penalty if explicitly matched to a known debunked narrative (30 pts)
            if best_overall_match and best_overall_match.is_known_debunked_narrative:
                score -= 30.0
        elif max_semantic_sim >= self.text_similarity_threshold or max_visual_sim >= 0.85:
            # Minor penalty for high similarity to standard recent posts
            score -= (max_semantic_sim * 15.0)

        similarity_score = round(max(0.0, min(100.0, score)), 2)
        match_status = "HISTORICAL_CORPUS_MATCH" if (max_semantic_sim >= self.text_similarity_threshold or max_visual_sim >= 0.85) else "NO_HISTORICAL_MATCH"

        # ----------------------------------------------------------------------
        # Step 7: Explanation Formulation
        # ----------------------------------------------------------------------
        if recycled_content:
            date_str = earliest_timestamp.strftime("%Y-%m-%d") if earliest_timestamp else "past archives"
            explanation = (
                f"Content matches archived material in local reference corpus (semantic similarity: {max_semantic_sim:.2f}, visual: {max_visual_sim:.2f}) "
                f"first seen {temporal_age_days:.0f} days ago ({date_str}). Note: Recycled content does not automatically prove malicious intent."
            )
        else:
            explanation = (
                f"Content demonstrates high originality; no matching recycled narrative found in current {corpus_count}-item local historical corpus "
                f"(max semantic similarity: {max_semantic_sim:.2f}, visual similarity: {max_visual_sim:.2f}, keyword overlap: {max_keyword_sim:.2f})."
            )

        return {
            "score": similarity_score,
            "similarity_score": similarity_score,
            "recycled_content": recycled_content,
            "visual_similarity": max_visual_sim,
            "semantic_similarity": max_semantic_sim,
            "keyword_similarity": max_keyword_sim,
            "matches": matches,
            "flags": flags,
            "explanation": explanation,
            "status": match_status,
            "similar_content_count": len(historical_items),
            "corpus_size": corpus_count,
            "text_similarity": max_semantic_sim,
            "image_similarity": max_visual_sim,
            "hashtag_similarity": max_keyword_sim,
            "earliest_matching_timestamp": earliest_timestamp.isoformat() if earliest_timestamp else None,
        }


similar_content_analyzer = SimilarContentAnalyzer()
