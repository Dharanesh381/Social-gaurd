"""End-to-End Analysis Pipeline Orchestrator Service."""

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
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
from app.services.persistence import VerificationPersistenceService
from app.utils.logging import logger


class AnalysisOrchestratorService:
    """Orchestrates incoming posts through Modules 1–5, AI detection, persistence, and explainability."""

    async def analyze_post(
        self,
        request_data: AnalysisRequest,
        db_session: AsyncSession | None = None,
    ) -> FinalAnalysisResult:
        """Execute the end-to-end verification pipeline."""
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
        if not post.comments:
            all_flags.append("NO_COMMENTS_AVAILABLE")
        if not post.media:
            all_flags.append("NO_MEDIA_ATTACHED")
        if post.timestamp is None:
            all_flags.append("NO_POST_TIMESTAMP")
        if post.author is None:
            all_flags.append("NO_AUTHOR_METADATA")

        module_breakdowns: dict[str, Any] = {}
        module_timing: dict[str, float] = {}

        # ----------------------------------------------------------------------
        # MODULE 1: COMMENT ANALYSIS (Async Wrapper)
        # ----------------------------------------------------------------------
        m1_start = time.perf_counter()
        try:
            m1_res = comment_analyzer.analyze(post.comments)
            module_timing["comment_analysis_ms"] = round((time.perf_counter() - m1_start) * 1000, 2)
            m1_score = m1_res.get("comment_score")
            comment_fact_check = m1_res.get("fact_check", {})
            module_breakdowns["comments"] = {
                "score": m1_score,
                "status": "COMPLETED",
                "metrics": m1_res.get("metrics", {}),
                "fact_check": comment_fact_check,
                "flags": m1_res.get("flags", []),
            }
            all_flags.extend(m1_res.get("flags", []))
            logger.info("Module 1 (Comments) finished in %sms | Score: %s | FactCheck Verdict: %s",
                        module_timing["comment_analysis_ms"], m1_score, comment_fact_check.get("verdict"))
        except Exception as exc:
            logger.error("Module 1 (Comments) failed: %s", exc)
            module_timing["comment_analysis_ms"] = round((time.perf_counter() - m1_start) * 1000, 2)
            m1_score = None
            comment_fact_check = {}
            module_breakdowns["comments"] = {
                "score": None,
                "status": "MODULE_ERROR",
                "error": str(exc),
                "metrics": {},
                "fact_check": {},
                "flags": ["COMMENT_ANALYSIS_FAILED"],
            }
            all_flags.append("COMMENT_ANALYSIS_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 2: EVIDENCE VERIFICATION (Async)
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
            module_breakdowns["evidence"] = {
                "score": m2_score,
                "status": m2_res.get("status", "NO_FACT_CHECK_FOUND"),
                "claims": m2_res.get("claims", []),
                "fact_checks": m2_res.get("fact_checks", []),
                "sources": m2_res.get("sources", []),
                "flags": m2_res.get("flags", []),
                "explanation": m2_res.get("explanation", ""),
            }
            all_flags.extend(m2_res.get("flags", []))
            logger.info("Module 2 (Evidence) finished in %sms | Score: %s | Status: %s", module_timing["evidence_verification_ms"], m2_score, m2_res.get("status"))
        except Exception as exc:
            logger.error("Module 2 (Evidence) failed: %s", exc)
            module_timing["evidence_verification_ms"] = round((time.perf_counter() - m2_start) * 1000, 2)
            m2_score = None
            module_breakdowns["evidence"] = {
                "score": None,
                "status": "MODULE_ERROR",
                "error": str(exc),
                "claims": [],
                "fact_checks": [],
                "flags": ["EVIDENCE_VERIFICATION_FAILED"],
                "explanation": "Evidence verification failed due to internal error.",
            }
            all_flags.append("EVIDENCE_VERIFICATION_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 3: USER BEHAVIOUR ANALYSIS
        # ----------------------------------------------------------------------
        m3_start = time.perf_counter()
        try:
            m3_res = user_behaviour_analyzer.analyze(post.author)
            module_timing["user_behaviour_ms"] = round((time.perf_counter() - m3_start) * 1000, 2)
            m3_score = m3_res.get("behaviour_score")
            module_breakdowns["user_behaviour"] = {
                "score": m3_score,
                "status": "COMPLETED",
                "anomaly_score": m3_res.get("anomaly_score", 0.0),
                "metrics": m3_res.get("metrics", {}),
                "flags": m3_res.get("flags", []),
                "explanation": m3_res.get("explanation", ""),
            }
            all_flags.extend(m3_res.get("flags", []))
            logger.info("Module 3 (User Behaviour) finished in %sms | Score: %s", module_timing["user_behaviour_ms"], m3_score)
        except Exception as exc:
            logger.error("Module 3 (User Behaviour) failed: %s", exc)
            module_timing["user_behaviour_ms"] = round((time.perf_counter() - m3_start) * 1000, 2)
            m3_score = None
            module_breakdowns["user_behaviour"] = {
                "score": None,
                "status": "MODULE_ERROR",
                "error": str(exc),
                "metrics": {},
                "flags": ["USER_BEHAVIOUR_ANALYSIS_FAILED"],
                "explanation": "User behaviour analysis failed due to internal error.",
            }
            all_flags.append("USER_BEHAVIOUR_ANALYSIS_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 4: SIMILAR CONTENT & TEMPORAL ANALYSIS (Async)
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
            m4_score = m4_res.get("similarity_score")
            module_breakdowns["similarity"] = {
                "score": m4_score,
                "status": "COMPLETED",
                "text_similarity": m4_res.get("text_similarity", 0.0),
                "image_similarity": m4_res.get("image_similarity", 0.0),
                "hashtag_similarity": m4_res.get("hashtag_similarity", 0.0),
                "recycled_content": m4_res.get("recycled_content", False),
                "earliest_matching_timestamp": m4_res.get("earliest_matching_timestamp"),
                "flags": m4_res.get("flags", []),
                "explanation": m4_res.get("explanation", ""),
            }
            all_flags.extend(m4_res.get("flags", []))
            logger.info("Module 4 (Similarity) finished in %sms | Score: %s", module_timing["similar_content_ms"], m4_score)
        except Exception as exc:
            logger.error("Module 4 (Similarity) failed: %s", exc)
            module_timing["similar_content_ms"] = round((time.perf_counter() - m4_start) * 1000, 2)
            m4_score = None
            module_breakdowns["similarity"] = {
                "score": None,
                "status": "MODULE_ERROR",
                "error": str(exc),
                "flags": ["SIMILAR_CONTENT_ANALYSIS_FAILED"],
                "explanation": "Similar content analysis failed due to internal error.",
            }
            all_flags.append("SIMILAR_CONTENT_ANALYSIS_FAILED")

        # ----------------------------------------------------------------------
        # MODULE 5: SCORE FUSION & DECISION
        # ----------------------------------------------------------------------
        m5_start = time.perf_counter()
        fusion_res = score_fusion_engine.fuse_scores(
            comment_score=m1_score,
            evidence_score=m2_score,
            behaviour_score=m3_score,
            similarity_score=m4_score,
            custom_weights=request_data.custom_weights,
        )
        module_timing["score_fusion_ms"] = round((time.perf_counter() - m5_start) * 1000, 2)
        module_breakdowns["fusion"] = fusion_res
        all_flags.extend(fusion_res.get("flags", []))

        final_credibility_score = fusion_res["final_score"]
        classification_str = fusion_res["classification"]
        classification_enum = CredibilityClassification(classification_str)

        # ----------------------------------------------------------------------
        # AI-GENERATED MEDIA / TEXT DETECTION (Decoupled Orthogonal Evaluation)
        # ----------------------------------------------------------------------
        ai_prob = None
        ai_details = {}
        if post.media and post.media[0].url:
            ai_media_res = await ai_media_detector.analyze_media_url(str(post.media[0].url))
            ai_prob = ai_media_res.get("ai_generation_probability")
            ai_details["media_ai_detection"] = ai_media_res

        # Fallback to text AI detection if media was not analyzable or missing
        if ai_prob is None and post.text:
            ai_text_res = ai_media_detector.analyze_text(post.text)
            ai_prob = ai_text_res.get("ai_generation_probability")
            ai_details["text_ai_detection"] = ai_text_res

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

        # ----------------------------------------------------------------------
        # PERSISTENCE (Store complete verification session in DB)
        # ----------------------------------------------------------------------
        persistence_payload = {
            "final_score": final_credibility_score,
            "classification": classification_str,
            "ai_generated_probability": ai_prob,
            "confidence_level": fusion_res.get("confidence_level", "MEDIUM"),
            "confidence_interval": fusion_res.get("confidence_interval", [None, None]),
            "summary_explanation": xai_res["summary"],
            "positive_factors": xai_res["positive_factors"],
            "negative_factors": xai_res["negative_factors"],
            "flags": list(set(all_flags)),
            "module_scores": {
                "comment_analysis": m1_score,
                "evidence_verification": m2_score,
                "user_behaviour": m3_score,
                "similar_content": m4_score,
            },
        }

        try:
            if db_session:
                await VerificationPersistenceService.save_verification_session(
                    session=db_session,
                    request_id=request_id,
                    post_data=post,
                    analysis_output=persistence_payload,
                    module_breakdowns=module_breakdowns,
                )
            else:
                async with AsyncSessionLocal() as fallback_db_session:
                    await VerificationPersistenceService.save_verification_session(
                        session=fallback_db_session,
                        request_id=request_id,
                        post_data=post,
                        analysis_output=persistence_payload,
                        module_breakdowns=module_breakdowns,
                    )
        except Exception as exc:
            logger.error("Failed to persist verification session to DB: %s", exc)
            all_flags.append("DB_PERSISTENCE_FAILED")

        logger.info(
            "Pipeline [%s] completed in %sms | Final Score: %.2f | Verdict: %s | AI Prob: %s",
            request_id,
            total_elapsed_ms,
            final_credibility_score,
            classification_str,
            f"{ai_prob:.1f}%" if ai_prob is not None else "None",
        )

        return FinalAnalysisResult(
            request_id=request_id,
            consolidated_score=final_credibility_score,
            classification=classification_enum,
            ai_generation_probability=round(ai_prob / 100.0, 4) if ai_prob is not None else None,
            explanation=xai_res["summary"],
            module_scores={
                "comment_analysis": m1_score,
                "evidence_verification": m2_score,
                "user_behaviour": m3_score,
                "similar_content": m4_score,
            },
            module_results={
                "timings_ms": module_timing,
                "module_breakdowns": module_breakdowns,
                "explainability": xai_res,
                "ai_detection": ai_details,
                "flags": list(set(all_flags)),
            },
            created_at=datetime.now(timezone.utc),
        )


orchestrator_service = AnalysisOrchestratorService()
