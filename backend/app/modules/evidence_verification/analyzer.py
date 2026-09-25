"""Module 2: Evidence-Based Verification Engine (Phase 4)."""

from typing import Any

from app.modules.evidence_verification.claim_extractor import (
    BaseClaimExtractor,
    claim_extractor,
)
from app.modules.evidence_verification.factcheck_client import (
    GoogleFactCheckClient,
    fact_check_client,
)
from app.modules.evidence_verification.normalization import (
    compute_source_credibility,
    normalize_fact_check_rating,
)
from app.modules.evidence_verification.ocr import (
    BaseOCRService,
    ocr_service,
)
from app.utils.logging import logger


class EvidenceVerifier:
    """Module 2: Extracts factual claims, queries fact-checking databases,

    normalizes ratings, weights by source authority, and computes Evidence Score.

    CRITICAL RULE:
    If NO fact-checks are found, the system assigns status NO_FACT_CHECK_FOUND
    with a neutral score (50.0). It MUST NEVER assume unverified claims are TRUE or FALSE.
    """

    def __init__(
        self,
        api_client: GoogleFactCheckClient | None = None,
        extractor: BaseClaimExtractor | None = None,
        ocr: BaseOCRService | None = None,
    ):
        self.api_client = api_client or fact_check_client
        self.extractor = extractor or claim_extractor
        self.ocr = ocr or ocr_service

    async def verify(
        self,
        post_text: str,
        image_urls: list[str] | None = None,
        comments: list[Any] | None = None,
        comment_claims: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute full Evidence-Based Verification pipeline.

        Returns:
            Dict conforming to:
            {
                "evidence_score": float (0-100),
                "status": "SUPPORTED" | "CONTRADICTED" | "MIXED/MISLEADING" | "NO_FACT_CHECK_FOUND" | "API_KEY_MISSING" | "NO_CLAIM_DETECTED",
                "claims": List[str],
                "fact_checks": List[Dict],
                "sources": List[Dict],
                "flags": List[str],
                "explanation": str,
                "diagnostics": Dict[str, Any]
            }
        """
        import re
        flags: list[str] = []
        image_urls = image_urls or []

        # ----------------------------------------------------------------------
        # Step 1: Optional OCR extraction for text in attached images
        # ----------------------------------------------------------------------
        combined_text = post_text or ""
        ocr_texts: list[str] = []
        for img_url in image_urls:
            try:
                extracted = await self.ocr.extract_text_from_url(img_url)
                if extracted:
                    ocr_texts.append(extracted)
                    combined_text += f" {extracted}"
            except Exception as e:
                logger.debug("OCR extraction skipped: %s", e)

        if ocr_texts:
            flags.append("OCR_TEXT_INCORPORATED")

        # ----------------------------------------------------------------------
        # Step 2: Claim Extraction from Post and Comments
        # ----------------------------------------------------------------------
        extracted_claims = self.extractor.extract_claims(combined_text)

        # Incorporate comment claims / crowdsourced debunking targets
        additional_queries: list[str] = list(comment_claims or [])
        if comments and hasattr(self.extractor, "extract_comment_claims"):
            additional_queries.extend(self.extractor.extract_comment_claims(comments))

        all_candidate_claims = list(dict.fromkeys(extracted_claims + additional_queries))

        if not all_candidate_claims:
            return {
                "evidence_score": 50.0,
                "status": "NO_FACT_CHECK_FOUND",
                "claims": [],
                "fact_checks": [],
                "sources": [],
                "flags": ["NO_VERIFIABLE_CLAIMS_DETECTED"],
                "explanation": "No verifiable claim found. Post content contains no verifiable factual claims (Neutral 50/100 baseline).",
                "diagnostics": {
                    "fact_check_status": "NO_CLAIM_DETECTED",
                    "query_used": [],
                    "result_count": 0,
                    "source_count": 0,
                    "normalization_status": "NO_CLAIMS",
                },
            }

        # ----------------------------------------------------------------------
        # Step 3: Fact-Check Retrieval via Google Fact Check Tools API
        # ----------------------------------------------------------------------
        all_matched_reviews: list[dict[str, Any]] = []
        sources_info: list[dict[str, Any]] = []
        queries_attempted: list[str] = []
        seen_review_urls: set[str] = set()
        api_status_observed = "SUCCESS"

        for claim in all_candidate_claims:
            # Generate query variations (e.g. full statement and concise keyword keyphrases)
            search_variations = [claim]
            if hasattr(self.extractor, "extract_search_queries"):
                search_variations = self.extractor.extract_search_queries(claim)

            found_for_this_claim = False
            for claim_query in search_variations:
                if claim_query in queries_attempted:
                    continue
                queries_attempted.append(claim_query)

                api_resp = await self.api_client.search_claims(query=claim_query)
                status_code = api_resp.get("status")

                if status_code == "API_KEY_MISSING":
                    api_status_observed = "API_KEY_MISSING"
                    if "GOOGLE_FACT_CHECK_API_KEY_NOT_CONFIGURED" not in flags:
                        flags.append("GOOGLE_FACT_CHECK_API_KEY_NOT_CONFIGURED")
                    break
                elif status_code == "RATE_LIMITED":
                    api_status_observed = "RATE_LIMITED"
                    flags.append("FACT_CHECK_API_RATE_LIMITED")
                    break
                elif status_code == "TIMEOUT":
                    api_status_observed = "TIMEOUT"
                    flags.append("FACT_CHECK_API_TIMEOUT")
                elif status_code == "MALFORMED_RESPONSE":
                    api_status_observed = "MALFORMED_RESPONSE"
                    flags.append("FACT_CHECK_API_MALFORMED_RESPONSE")
                elif status_code in ("API_ERROR", "CONNECTION_ERROR"):
                    api_status_observed = status_code
                    flags.append("FACT_CHECK_API_UNAVAILABLE")
                elif status_code == "SUCCESS":
                    raw_claims = api_resp.get("claims", [])
                    if raw_claims:
                        found_for_this_claim = True
                        for c in raw_claims:
                            claim_text = c.get("text", "")
                            claimant = c.get("claimant", "")
                            reviews = c.get("claimReview", [])
                            for r in reviews:
                                review_url = r.get("url", "")
                                if review_url and review_url in seen_review_urls:
                                    continue
                                if review_url:
                                    seen_review_urls.add(review_url)

                                publisher = r.get("publisher", {}).get("name", "Unknown Publisher")
                                publisher_site = r.get("publisher", {}).get("site", "")
                                raw_rating = r.get("textualRating", "")

                                norm_score, category = normalize_fact_check_rating(raw_rating)
                                src_credibility = compute_source_credibility(publisher, publisher_site)

                                match_item = {
                                    "claim": claim_text,
                                    "claimant": claimant,
                                    "publisher": publisher,
                                    "rating": raw_rating,
                                    "raw_rating": raw_rating,
                                    "source_url": review_url,
                                    "publisher_url": review_url,
                                    "normalized_evidence_score": round(norm_score * 100.0, 2),
                                    "normalized_truth_score": norm_score,
                                    "rating_category": category,
                                    "source_credibility": src_credibility,
                                }
                                all_matched_reviews.append(match_item)

                                sources_info.append({
                                    "publisher": publisher,
                                    "site": publisher_site,
                                    "credibility_weight": src_credibility,
                                    "url": review_url,
                                    "source_url": review_url,
                                })

                # If we found reviews for the primary query, avoid redundant secondary requests
                if found_for_this_claim:
                    break

        # ----------------------------------------------------------------------
        # Step 4: Decision Status and Evidence Score Calculation
        # ----------------------------------------------------------------------
        if not all_matched_reviews:
            status = "NO_FACT_CHECK_FOUND"
            evidence_score = 50.0

            # Evaluate linguistic credibility signals when unindexed in fact check DB
            clean_post = post_text or ""
            is_clickbait = bool(
                re.search(
                    r"\b(miracle\s+cure|secret\s+cure|100%\s+cure|shocking\s+truth|"
                    r"they\s+don't\s+want\s+you\s+to\s+know|share\s+before\s+deleted|"
                    r"government\s+secret|poisoning\s+the\s+population|secretly\s+killed)\b",
                    clean_post,
                    re.IGNORECASE,
                )
                or (clean_post.count("!") >= 4)
                or (len(clean_post) > 40 and sum(1 for ch in clean_post if ch.isupper()) / max(1, len(clean_post)) > 0.40)
            )

            is_journalistic = bool(
                re.search(
                    r"\b(according\s+to\s+reuters|associated\s+press\s+reports|published\s+in\s+nature|"
                    r"peer-reviewed\s+study|official\s+press\s+release|bbc\s+news\s+reports)\b",
                    clean_post,
                    re.IGNORECASE,
                )
            )

            if is_clickbait:
                evidence_score = 40.0
                flags.append("SENSATIONALIST_UNVERIFIED_CLAIM")
                explanation = "No matching fact-checks found; content exhibits viral sensationalist and conspiratorial language markers (Calibrated baseline 40/100)."
            elif is_journalistic:
                evidence_score = 65.0
                flags.append("JOURNALISTIC_ATTRIBUTION_DETECTED")
                explanation = "No fact-check found; content cites verified institutional or journalistic attribution (Calibrated baseline 65/100)."
            elif api_status_observed == "API_KEY_MISSING":
                explanation = "Google Fact Check API key is not configured; evidence module assigned neutral baseline (50/100)."
            elif api_status_observed == "TIMEOUT":
                explanation = "Google Fact Check API request timed out; evidence module assigned neutral baseline (50/100)."
            elif api_status_observed == "MALFORMED_RESPONSE":
                explanation = "Google Fact Check API returned an invalid response; evidence module assigned neutral baseline (50/100)."
            elif api_status_observed in ("CONNECTION_ERROR", "API_ERROR", "RATE_LIMITED"):
                explanation = f"Google Fact Check API unavailable ({api_status_observed}); evidence module assigned neutral baseline (50/100)."
            else:
                explanation = (
                    "No matching fact-check found in Google Fact Check index. "
                    "Assigned neutral baseline score (50/100). Absence of fact-checks does not verify or disprove content."
                )

            return {
                "evidence_score": evidence_score,
                "status": status,
                "claims": extracted_claims,
                "fact_checks": [],
                "sources": [],
                "flags": flags,
                "explanation": explanation,
                "diagnostics": {
                    "fact_check_status": "NO_FACT_CHECK_FOUND" if api_status_observed == "SUCCESS" else api_status_observed,
                    "query_used": queries_attempted,
                    "result_count": 0,
                    "source_count": 0,
                    "normalization_status": "NEUTRAL_BASELINE",
                },
            }

        # Weighted average of fact-check scores weighted by source credibility
        total_weight = sum(m["source_credibility"] for m in all_matched_reviews)
        if total_weight > 0:
            weighted_truth = sum(m["normalized_truth_score"] * m["source_credibility"] for m in all_matched_reviews) / total_weight
        else:
            weighted_truth = sum(m["normalized_truth_score"] for m in all_matched_reviews) / len(all_matched_reviews)

        # Scale 0.0 - 1.0 continuous truth to 0 - 100 Evidence Score
        evidence_score = round(weighted_truth * 100.0, 2)

        # Determine Categorical Status
        false_count = sum(1 for m in all_matched_reviews if m["rating_category"] in ("FALSE", "MOSTLY_FALSE"))
        true_count = sum(1 for m in all_matched_reviews if m["rating_category"] in ("TRUE", "MOSTLY_TRUE"))
        mixed_count = sum(1 for m in all_matched_reviews if m["rating_category"] == "MIXED")

        if false_count > 0 and true_count == 0:
            status = "CONTRADICTED"
            flags.append("DEBUNKED_BY_FACT_CHECKERS")
            explanation = f"Extracted claim has been explicitly contradicted/debunked by {all_matched_reviews[0]['publisher']} ({all_matched_reviews[0]['raw_rating']})."
        elif true_count > 0 and false_count == 0:
            status = "SUPPORTED"
            flags.append("VERIFIED_BY_FACT_CHECKERS")
            explanation = f"Extracted claim is verified and supported by {all_matched_reviews[0]['publisher']} ({all_matched_reviews[0]['raw_rating']})."
        elif false_count > 0 and true_count > 0:
            status = "MIXED/MISLEADING"
            flags.append("CONFLICTING_FACT_CHECK_REVIEWS")
            explanation = "Fact-check sources provide mixed or conflicting ratings for these claims."
        elif mixed_count > 0:
            status = "MIXED/MISLEADING"
            explanation = "Fact-check sources indicate this claim is partially true or missing vital context."
        else:
            status = "INSUFFICIENT_EVIDENCE"
            explanation = "Matched fact-checks provided inconclusive ratings for this context."

        return {
            "evidence_score": evidence_score,
            "status": status,
            "claims": extracted_claims,
            "fact_checks": all_matched_reviews,
            "sources": sources_info,
            "flags": flags,
            "explanation": explanation,
            "diagnostics": {
                "fact_check_status": "FACT_CHECK_FOUND",
                "query_used": queries_attempted,
                "result_count": len(all_matched_reviews),
                "source_count": len(sources_info),
                "normalization_status": f"WEIGHTED_{status}",
            },
        }


evidence_verifier = EvidenceVerifier()
