"""End-to-End Analysis Pipeline Orchestrator Service."""

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.modules.comment_analysis.analyzer import comment_analyzer
from app.modules.evidence_verification.analyzer import evidence_verifier
from app.modules.score_fusion.ai_detector import ai_media_detector
from app.modules.score_fusion.engine import score_fusion_engine
from app.modules.score_fusion.explainability import explainability_engine
from app.modules.similar_content.analyzer import similar_content_analyzer
from app.modules.user_behaviour.analyzer import user_behaviour_analyzer
from app.schemas.domain_models import (
    AnalysisRequest,
    CredibilityClassification,
    FinalAnalysisResult,
)
from app.utils.logging import logger


class AnalysisOrchestratorService:
    """Orchestrates incoming posts in memory through Modules 1–5, AI detection, and explainability."""

    async def analyze_post(
        self,
        request_data: AnalysisRequest,
    ) -> FinalAnalysisResult:
        """Execute the end-to-end in-memory verification pipeline."""
        start_time = time.perf_counter()
        request_id = request_data.request_id or f"sg_req_{uuid.uuid4().hex[:12]}"
        post = request_data.post

        logger.info(
            "Starting live verification pipeline [%s] | Platform: %s | Post Text: %.40s... | Comments: %d | Media URLs: %d",
            request_id,
            post.platform,
            post.text,
            len(post.comments),
            len(post.media),
        )

        all_flags: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        if not post.comments:
            all_flags.append("NO_COMMENTS_AVAILABLE")
            warnings.append("No comments provided; Module 1 evaluated as UNAVAILABLE baseline.")
        if not post.media:
            all_flags.append("NO_MEDIA_ATTACHED")
        if post.timestamp is None:
            all_flags.append("NO_POST_TIMESTAMP")
            warnings.append("No post timestamp provided; temporal age delta calculated from current time.")
        if post.author is None:
            all_flags.append("NO_AUTHOR_METADATA")
            warnings.append("No author profile metadata provided; Module 3 evaluated as UNAVAILABLE baseline.")

        module_breakdowns: dict[str, Any] = {}
        module_timing: dict[str, float] = {}

        # ----------------------------------------------------------------------
        # MODULE 1: COMMENT ANALYSIS
        # ----------------------------------------------------------------------
        m1_start = time.perf_counter()
        try:
            m1_res = comment_analyzer.analyze(post.comments)
            module_timing["comment_analysis_ms"] = round((time.perf_counter() - m1_start) * 1000, 2)
            m1_score = m1_res.get("comment_score")
            comment_fact_check = m1_res.get("fact_check", {})

            if not post.comments:
                m1_status = "UNAVAILABLE"
            elif len(post.comments) <= 2:
                m1_status = "PARTIAL"
            else:
                m1_status = "COMPLETED"

            m1_output = {
                "score": m1_score,
                "status": m1_status,
                "comment_count": len(post.comments),
                "duplicate_ratio": m1_res.get("duplicate_ratio", 0.0),
                "semantic_similarity": m1_res.get("semantic_similarity", 0.0),
                "clusters": m1_res.get("clusters", []),
                "temporal_burst_score": m1_res.get("temporal_burst_score", 0.0),
                "z_score": m1_res.get("z_score", 0.0),
                "iqr_outliers": m1_res.get("iqr_outliers", []),
                "emoji_entropy": m1_res.get("emoji_entropy", 0.0),
                "debunk_ratio": m1_res.get("debunk_ratio", 0.0),
                "support_ratio": m1_res.get("support_ratio", 0.0),
                "flags": m1_res.get("flags", []),
                "explanation": m1_res.get("explanation", ""),
                "metrics": m1_res.get("metrics", {}),
                "fact_check": comment_fact_check,
            }
            module_breakdowns["comments"] = m1_output
            all_flags.extend(m1_res.get("flags", []))
            logger.info("Module 1 (Comments) finished in %sms | Status: %s | Score: %s",
                        module_timing["comment_analysis_ms"], m1_status, m1_score)
        except Exception as exc:
            logger.error("Module 1 (Comments) failed: %s", exc)
            module_timing["comment_analysis_ms"] = round((time.perf_counter() - m1_start) * 1000, 2)
            m1_score = None
            comment_fact_check = {}
            m1_status = "ERROR"
            errors.append(f"Module 1 (Comment Analysis) error: {exc}")
            m1_output = {
                "score": None,
                "status": m1_status,
                "error": str(exc),
                "comment_count": len(post.comments),
                "flags": ["COMMENT_ANALYSIS_FAILED"],
                "explanation": "Comment analysis failed due to an internal error.",
            }
            module_breakdowns["comments"] = m1_output
            all_flags.append("COMMENT_ANALYSIS_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 2: EVIDENCE VERIFICATION
        # ----------------------------------------------------------------------
        m2_start = time.perf_counter()
        try:
            img_urls = [str(m.url) for m in post.media if m.url]
            m2_res = await evidence_verifier.verify(
                post_text=post.text,
                image_urls=img_urls,
                comments=post.comments,
                comment_claims=comment_fact_check.get("extracted_comment_claims", []),
            )
            module_timing["evidence_verification_ms"] = round((time.perf_counter() - m2_start) * 1000, 2)
            m2_score = m2_res.get("evidence_score")

            ev_state = m2_res.get("status", "NO_FACT_CHECK_FOUND")
            if ev_state in ("SUPPORTED", "CONTRADICTED", "MIXED/MISLEADING"):
                m2_status = "COMPLETED"
            else:
                m2_status = "PARTIAL"
                warnings.append("No definitive fact-checks indexed for post claim; evaluated at neutral baseline.")

            m2_output = {
                "score": m2_score,
                "status": m2_status,
                "evidence_state": ev_state,
                "claims": m2_res.get("claims", []),
                "fact_checks": m2_res.get("fact_checks", []),
                "verified_count": m2_res.get("verified_count", 0),
                "false_count": m2_res.get("false_count", 0),
                "unverified_count": m2_res.get("unverified_count", 0),
                "source_quality": m2_res.get("source_quality", 0.5),
                "sources": m2_res.get("sources", []),
                "flags": m2_res.get("flags", []),
                "explanation": m2_res.get("explanation", ""),
            }
            module_breakdowns["evidence"] = m2_output
            all_flags.extend(m2_res.get("flags", []))
            logger.info("Module 2 (Evidence) finished in %sms | Status: %s | Score: %s",
                        module_timing["evidence_verification_ms"], m2_status, m2_score)
        except Exception as exc:
            logger.error("Module 2 (Evidence) failed: %s", exc)
            module_timing["evidence_verification_ms"] = round((time.perf_counter() - m2_start) * 1000, 2)
            m2_score = None
            m2_status = "ERROR"
            errors.append(f"Module 2 (Evidence Verification) error: {exc}")
            m2_output = {
                "score": None,
                "status": m2_status,
                "error": str(exc),
                "claims": [],
                "fact_checks": [],
                "flags": ["EVIDENCE_VERIFICATION_FAILED"],
                "explanation": "Evidence verification failed due to an internal error.",
            }
            module_breakdowns["evidence"] = m2_output
            all_flags.append("EVIDENCE_VERIFICATION_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 3: USER BEHAVIOUR ANALYSIS
        # ----------------------------------------------------------------------
        m3_start = time.perf_counter()
        try:
            m3_res = user_behaviour_analyzer.analyze(post.author)
            module_timing["user_behaviour_ms"] = round((time.perf_counter() - m3_start) * 1000, 2)
            m3_score = m3_res.get("behaviour_score")

            if post.author is None:
                m3_status = "UNAVAILABLE"
            else:
                m3_status = "COMPLETED"

            m3_output = {
                "score": m3_score,
                "status": m3_status,
                "anomaly_score": m3_res.get("anomaly_score", 0.0),
                "is_anomalous": m3_res.get("is_anomalous", False),
                "metrics": m3_res.get("metrics", {}),
                "flags": m3_res.get("flags", []),
                "explanation": m3_res.get("explanation", ""),
            }
            module_breakdowns["user_behaviour"] = m3_output
            all_flags.extend(m3_res.get("flags", []))
            logger.info("Module 3 (User Behaviour) finished in %sms | Status: %s | Score: %s",
                        module_timing["user_behaviour_ms"], m3_status, m3_score)
        except Exception as exc:
            logger.error("Module 3 (User Behaviour) failed: %s", exc)
            module_timing["user_behaviour_ms"] = round((time.perf_counter() - m3_start) * 1000, 2)
            m3_score = None
            m3_status = "ERROR"
            errors.append(f"Module 3 (User Behaviour) error: {exc}")
            m3_output = {
                "score": None,
                "status": m3_status,
                "error": str(exc),
                "metrics": {},
                "flags": ["USER_BEHAVIOUR_ANALYSIS_FAILED"],
                "explanation": "User behaviour analysis failed due to an internal error.",
            }
            module_breakdowns["user_behaviour"] = m3_output
            all_flags.append("USER_BEHAVIOUR_ANALYSIS_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 4: SIMILAR CONTENT & TEMPORAL ANALYSIS
        # ----------------------------------------------------------------------
        m4_start = time.perf_counter()
        try:
            first_img_url = [str(m.url) for m in post.media if m.url]
            first_img = first_img_url[0] if first_img_url else None
            m4_res = await similar_content_analyzer.analyze(
                text=post.text,
                hashtags=post.hashtags,
                image_urls=[first_img] if first_img else [],
                post_timestamp=post.timestamp,
            )
            module_timing["similar_content_ms"] = round((time.perf_counter() - m4_start) * 1000, 2)
            m4_score = m4_res.get("score", m4_res.get("similarity_score"))

            if not post.text.strip() and not first_img:
                m4_status = "UNAVAILABLE"
            elif "IMAGE_HASH_EXTRACTION_UNAVAILABLE" in m4_res.get("flags", []):
                m4_status = "PARTIAL"
                warnings.append("Attached image could not be fetched for perceptual hashing; analyzed text only.")
            else:
                m4_status = "COMPLETED"

            m4_output = {
                "score": m4_score,
                "status": m4_status,
                "recycled_content": m4_res.get("recycled_content", False),
                "visual_similarity": m4_res.get("visual_similarity", m4_res.get("image_similarity", 0.0)),
                "semantic_similarity": m4_res.get("semantic_similarity", m4_res.get("text_similarity", 0.0)),
                "keyword_similarity": m4_res.get("keyword_similarity", m4_res.get("hashtag_similarity", 0.0)),
                "matches": m4_res.get("matches", []),
                "flags": m4_res.get("flags", []),
                "explanation": m4_res.get("explanation", ""),
                "earliest_matching_timestamp": m4_res.get("earliest_matching_timestamp"),
                "corpus_size": m4_res.get("corpus_size", 3),
            }
            module_breakdowns["similarity"] = m4_output
            all_flags.extend(m4_res.get("flags", []))
            logger.info("Module 4 (Similarity) finished in %sms | Status: %s | Score: %s",
                        module_timing["similar_content_ms"], m4_status, m4_score)
        except Exception as exc:
            logger.error("Module 4 (Similarity) failed: %s", exc)
            module_timing["similar_content_ms"] = round((time.perf_counter() - m4_start) * 1000, 2)
            m4_score = None
            m4_status = "ERROR"
            errors.append(f"Module 4 (Similar Content) error: {exc}")
            m4_output = {
                "score": None,
                "status": m4_status,
                "error": str(exc),
                "recycled_content": False,
                "flags": ["SIMILAR_CONTENT_ANALYSIS_FAILED"],
                "explanation": "Similar content analysis failed due to an internal error.",
            }
            module_breakdowns["similarity"] = m4_output
            all_flags.append("SIMILAR_CONTENT_ANALYSIS_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 5: SCORE FUSION & DECISION
        # ----------------------------------------------------------------------
        m5_start = time.perf_counter()
        try:
            fusion_res = score_fusion_engine.fuse_scores(
                comment_score=m1_score,
                evidence_score=m2_score,
                behaviour_score=m3_score,
                similarity_score=m4_score,
                custom_weights=request_data.custom_weights,
            )
            module_timing["score_fusion_ms"] = round((time.perf_counter() - m5_start) * 1000, 2)

            m5_status = "PARTIAL" if any(s == "ERROR" for s in [m1_status, m2_status, m3_status, m4_status]) else "COMPLETED"
            final_credibility_score = fusion_res["final_score"]
            classification_str = fusion_res["classification"]
            classification_enum = CredibilityClassification(classification_str)

            m5_output = {
                "final_score": final_credibility_score,
                "score": final_credibility_score,
                "status": m5_status,
                "classification": classification_str,
                "confidence_level": fusion_res.get("confidence_level", "MEDIUM"),
                "confidence_interval": fusion_res.get("confidence_interval", [final_credibility_score, final_credibility_score]),
                "formula_applied": fusion_res.get("formula_applied", "0.20*M1 + 0.40*M2 + 0.15*M3 + 0.25*M4"),
                "weights_applied": fusion_res.get("weights_applied", {}),
                "module_scores": {
                    "comment_analysis": m1_score if m1_score is not None else 50.0,
                    "evidence_verification": m2_score if m2_score is not None else 50.0,
                    "user_behaviour": m3_score if m3_score is not None else 50.0,
                    "similar_content": m4_score if m4_score is not None else 50.0,
                },
                "weighted_contributions": fusion_res.get("weighted_contributions", {}),
                "flags": fusion_res.get("flags", []),
                "summary_explanation": fusion_res.get("summary_explanation", ""),
            }
            module_breakdowns["fusion"] = m5_output
            all_flags.extend(fusion_res.get("flags", []))
        except Exception as exc:
            logger.error("Module 5 (Score Fusion) failed: %s", exc)
            module_timing["score_fusion_ms"] = round((time.perf_counter() - m5_start) * 1000, 2)
            m5_status = "ERROR"
            errors.append(f"Module 5 (Score Fusion) error: {exc}")
            final_credibility_score = 50.0
            classification_str = CredibilityClassification.UNCERTAIN.value
            classification_enum = CredibilityClassification.UNCERTAIN
            m5_output = {
                "final_score": 50.0,
                "score": 50.0,
                "status": m5_status,
                "classification": classification_str,
                "confidence_level": "LOW",
                "error": str(exc),
                "formula_applied": "0.20*M1 + 0.40*M2 + 0.15*M3 + 0.25*M4",
                "weights_applied": {},
                "module_scores": {},
                "weighted_contributions": {},
                "flags": ["SCORE_FUSION_ERROR"],
                "summary_explanation": "Score fusion failed; defaulted to neutral UNCERTAIN baseline.",
            }
            module_breakdowns["fusion"] = m5_output

        # ----------------------------------------------------------------------
        # AI-GENERATED MEDIA / TEXT DETECTION (Decoupled Orthogonal Evaluation)
        # ----------------------------------------------------------------------
        ai_start = time.perf_counter()
        ai_prob = None
        ai_details = {}
        if post.media and post.media[0].url:
            ai_media_res = await ai_media_detector.analyze_media_url(str(post.media[0].url))
            ai_prob = ai_media_res.get("ai_generation_probability")
            ai_details["media_ai_detection"] = ai_media_res

        if ai_prob is None and post.text:
            ai_text_res = ai_media_detector.analyze_text(post.text)
            ai_prob = ai_text_res.get("ai_generation_probability")
            ai_details["text_ai_detection"] = ai_text_res
        module_timing["ai_detection_ms"] = round((time.perf_counter() - ai_start) * 1000, 2)

        # ----------------------------------------------------------------------
        # EXPLAINABILITY ENGINE (Reasoning & Factor Ranking)
        # ----------------------------------------------------------------------
        xai_start = time.perf_counter()
        xai_res = explainability_engine.generate_explanation(
            final_score=final_credibility_score,
            classification=classification_str,
            module_breakdowns=module_breakdowns,
            ai_generated_probability=ai_prob,
        )
        module_timing["explainability_ms"] = round((time.perf_counter() - xai_start) * 1000, 2)

        total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        module_timing["total_pipeline_ms"] = total_elapsed_ms

        logger.info(
            "Pipeline [%s] completed in %sms | Final Score: %.2f | Verdict: %s | AI Prob: %s",
            request_id,
            total_elapsed_ms,
            final_credibility_score,
            classification_str,
            f"{ai_prob:.1f}%" if ai_prob is not None else "None",
        )

        # ----------------------------------------------------------------------
        # CONSTRUCT COMPLETE PRODUCTION JSON RESPONSE
        # ----------------------------------------------------------------------
        request_info = {
            "request_id": request_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "has_custom_weights": request_data.custom_weights is not None,
        }

        post_info = {
            "platform": post.platform,
            "post_id": post.post_id,
            "text": post.text,
            "text_length": len(post.text),
            "timestamp": post.timestamp.isoformat() if post.timestamp else None,
            "hashtags": post.hashtags,
            "media_count": len(post.media),
            "media_urls": [str(m.url) for m in post.media if m.url],
            "comments_count": len(post.comments),
            "has_author_metadata": post.author is not None,
            "author_username": post.author.username if post.author else None,
        }

        processing_timings = {
            "module_1_comments_ms": module_timing.get("comment_analysis_ms", 0.0),
            "module_2_evidence_ms": module_timing.get("evidence_verification_ms", 0.0),
            "module_3_behaviour_ms": module_timing.get("user_behaviour_ms", 0.0),
            "module_4_similarity_ms": module_timing.get("similar_content_ms", 0.0),
            "module_5_fusion_ms": module_timing.get("score_fusion_ms", 0.0),
            "ai_detection_ms": module_timing.get("ai_detection_ms", 0.0),
            "explainability_ms": module_timing.get("explainability_ms", 0.0),
            "total_pipeline_ms": total_elapsed_ms,
        }

        xai_explanation = {
            "summary": xai_res.get("summary", ""),
            "explanation_summary": xai_res.get("summary", ""),
            "positive_factors": xai_res.get("positive_factors", []),
            "negative_factors": xai_res.get("negative_factors", []),
            "module_explanations": xai_res.get("module_explanations", {}),
            "confidence_notes": xai_res.get("confidence_notes", []),
        }

        return FinalAnalysisResult(
            request_id=request_id,
            consolidated_score=final_credibility_score,
            classification=classification_enum,
            ai_generation_probability=round(ai_prob / 100.0, 4) if ai_prob is not None else None,
            explanation=xai_res.get("summary", ""),
            module_scores={
                "comment_analysis": m1_score,
                "evidence_verification": m2_score,
                "user_behaviour": m3_score,
                "similar_content": m4_score,
            },
            request_info=request_info,
            post_info=post_info,
            module_1=m1_output,
            module_2=m2_output,
            module_3=m3_output,
            module_4=m4_output,
            module_5=m5_output,
            xai_explanation=xai_explanation,
            processing_timings=processing_timings,
            warnings=warnings,
            errors=errors,
            module_results={
                "timings_ms": module_timing,
                "module_breakdowns": module_breakdowns,
                "explainability": xai_res,
                "ai_detection": ai_details,
                "flags": list(set(all_flags)),
                "warnings": warnings,
                "errors": errors,
            },
            created_at=datetime.now(timezone.utc),
        )


orchestrator_service = AnalysisOrchestratorService()

