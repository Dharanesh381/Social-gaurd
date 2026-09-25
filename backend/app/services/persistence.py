"""Database access and verification session persistence service."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AnalysisResultModel,
    CommentModel,
    EvidenceModel,
    PostModel,
    UserModel,
)
from app.schemas.domain_models import SocialMediaPost, UserProfile

logger = logging.getLogger(__name__)


def _scrub_sensitive_data(data: Any) -> Any:
    """Recursively scrub any sensitive keys (API keys, secrets, tokens) from dictionaries."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ("key", "secret", "token", "password", "auth", "credential")):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = _scrub_sensitive_data(v)
        return cleaned
    elif isinstance(data, list):
        return [_scrub_sensitive_data(item) for item in data]
    return data


class VerificationPersistenceService:
    """Service to persist verification sessions, posts, comments, evidence, and results."""

    @staticmethod
    async def get_or_create_user(session: AsyncSession, profile: UserProfile | None) -> UserModel | None:
        """Fetch existing user by username or create a new user record."""
        if not profile or not profile.username:
            return None

        username_clean = str(profile.username).strip()
        if not username_clean:
            return None

        stmt = select(UserModel).where(UserModel.username == username_clean)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user is None:
            user = UserModel(
                username=username_clean,
                account_age_days=profile.account_age_days,
                followers=profile.followers or 0,
                following=profile.following or 0,
                posts_per_day=profile.posts_per_day or 0.0,
                comments_per_day=profile.comments_per_day or 0.0,
                engagement_rate=profile.engagement_rate,
                duplicate_content_ratio=profile.duplicate_content_ratio,
                hashtag_repetition_rate=profile.hashtag_repetition_rate,
            )
            session.add(user)
            await session.flush()
        else:
            # Update latest behavioural markers
            if profile.followers is not None:
                user.followers = profile.followers
            if profile.following is not None:
                user.following = profile.following
            if profile.account_age_days is not None:
                user.account_age_days = profile.account_age_days
            if profile.posts_per_day is not None:
                user.posts_per_day = profile.posts_per_day
            if profile.comments_per_day is not None:
                user.comments_per_day = profile.comments_per_day
            if profile.engagement_rate is not None:
                user.engagement_rate = profile.engagement_rate
            if profile.duplicate_content_ratio is not None:
                user.duplicate_content_ratio = profile.duplicate_content_ratio
            if profile.hashtag_repetition_rate is not None:
                user.hashtag_repetition_rate = profile.hashtag_repetition_rate

        return user

    @classmethod
    async def save_verification_session(
        cls,
        session: AsyncSession,
        request_id: str,
        post_data: SocialMediaPost,
        analysis_output: dict[str, Any],
        module_breakdowns: dict[str, Any],
    ) -> AnalysisResultModel:
        """Persist a complete Social Guard verification session across relational tables."""
        # 0. Deduplication check: Avoid duplicate records where request IDs already provide uniqueness
        stmt = select(AnalysisResultModel).where(AnalysisResultModel.request_id == request_id)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing is not None:
            logger.info("Verification session with request_id [%s] already exists in database. Skipping duplicate persistence.", request_id)
            return existing

        try:
            # 1. Author record
            author_user = await cls.get_or_create_user(session, post_data.author)

            # 2. Post record
            post_record = PostModel(
                platform_post_id=post_data.post_id,
                platform=post_data.platform,
                text=post_data.text,
                hashtags=post_data.hashtags,
                media_urls=[str(m.url) for m in post_data.media],
                post_timestamp=post_data.timestamp,
                author_id=author_user.id if author_user else None,
            )
            session.add(post_record)
            await session.flush()

            # 3. Comment records
            for c in post_data.comments:
                c_profile = c.author
                if not c_profile and c.author_id:
                    c_profile = UserProfile(username=str(c.author_id).strip())
                comment_author = await cls.get_or_create_user(session, c_profile)
                comment_record = CommentModel(
                    post_id=post_record.id,
                    author_id=comment_author.id if comment_author else None,
                    comment_platform_id=c.comment_id,
                    text=c.text,
                    likes=c.likes,
                    emojis=c.emojis,
                    emoji_count=c.emoji_count or len(c.emojis),
                    comment_timestamp=c.timestamp,
                )
                session.add(comment_record)

            # 4. Evidence records (Fact-checks and extracted claims)
            ev_data = module_breakdowns.get("evidence", {})
            fact_checks = ev_data.get("fact_checks", [])
            if fact_checks:
                for fc in fact_checks:
                    ev_record = EvidenceModel(
                        post_id=post_record.id,
                        claim_text=fc.get("claim", "") or "",
                        status=ev_data.get("status", "NO_FACT_CHECK_FOUND"),
                        publisher=fc.get("publisher"),
                        publisher_url=fc.get("publisher_url") or fc.get("source_url"),
                        raw_rating=fc.get("raw_rating") or fc.get("rating"),
                        normalized_truth_score=fc.get("normalized_truth_score"),
                        source_credibility_weight=fc.get("source_credibility") or fc.get("source_credibility_weight"),
                        ocr_extracted_text=ev_data.get("ocr_extracted_text"),
                        raw_response_metadata=_scrub_sensitive_data(fc),
                    )
                    session.add(ev_record)
            elif ev_data.get("claims"):
                for claim_item in ev_data.get("claims", []):
                    claim_text = claim_item if isinstance(claim_item, str) else str(claim_item)
                    ev_record = EvidenceModel(
                        post_id=post_record.id,
                        claim_text=claim_text,
                        status=ev_data.get("status", "NO_FACT_CHECK_FOUND"),
                        publisher=None,
                        publisher_url=None,
                        raw_rating=None,
                        normalized_truth_score=0.5,
                        source_credibility_weight=0.0,
                        ocr_extracted_text=ev_data.get("ocr_extracted_text"),
                    )
                    session.add(ev_record)

            # 5. Robust Module Score Extraction
            m_scores = analysis_output.get("module_scores", {})
            comment_score = (
                m_scores.get("comment_analysis")
                if m_scores.get("comment_analysis") is not None
                else module_breakdowns.get("comments", {}).get("score")
                if module_breakdowns.get("comments", {}).get("score") is not None
                else module_breakdowns.get("comments", {}).get("sentiment_stance_score")
            )
            evidence_score = (
                m_scores.get("evidence_verification")
                if m_scores.get("evidence_verification") is not None
                else module_breakdowns.get("evidence", {}).get("score")
                if module_breakdowns.get("evidence", {}).get("score") is not None
                else module_breakdowns.get("evidence", {}).get("evidence_score")
            )
            behaviour_score = (
                m_scores.get("user_behaviour")
                if m_scores.get("user_behaviour") is not None
                else module_breakdowns.get("user_behaviour", {}).get("score")
                if module_breakdowns.get("user_behaviour", {}).get("score") is not None
                else module_breakdowns.get("user_behaviour", {}).get("behaviour_credibility_score")
            )
            similarity_score = (
                m_scores.get("similar_content")
                if m_scores.get("similar_content") is not None
                else module_breakdowns.get("similarity", {}).get("score")
                if module_breakdowns.get("similarity", {}).get("score") is not None
                else module_breakdowns.get("similarity", {}).get("similarity_score")
            )

            # 6. Analysis Result Record
            conf_int = analysis_output.get("confidence_interval", [None, None])
            sanitized_breakdowns = _scrub_sensitive_data(module_breakdowns)

            result_record = AnalysisResultModel(
                request_id=request_id,
                post_id=post_record.id,
                final_score=analysis_output["final_score"],
                classification=analysis_output["classification"],
                ai_generated_probability=analysis_output.get("ai_generated_probability"),
                confidence_level=analysis_output.get("confidence_level", "MEDIUM"),
                confidence_interval_low=conf_int[0] if len(conf_int) > 0 else None,
                confidence_interval_high=conf_int[1] if len(conf_int) > 1 else None,
                comment_score=comment_score,
                evidence_score=evidence_score,
                behaviour_score=behaviour_score,
                similarity_score=similarity_score,
                explanation_summary=analysis_output.get("summary_explanation", ""),
                positive_factors=analysis_output.get("positive_factors", []),
                negative_factors=analysis_output.get("negative_factors", []),
                module_breakdowns=sanitized_breakdowns,
                flags=analysis_output.get("flags", []),
            )
            session.add(result_record)
            await session.commit()
            await session.refresh(result_record)

            logger.info("Persisted verification session [%s] for post id %d", request_id, post_record.id)
            return result_record
        except Exception as exc:
            await session.rollback()
            logger.error("Failed to persist verification session [%s]: %s", request_id, exc)
            raise exc


persistence_service = VerificationPersistenceService()
