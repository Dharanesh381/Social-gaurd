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


class VerificationPersistenceService:
    """Service to persist verification sessions, posts, comments, evidence, and results."""

    @staticmethod
    async def get_or_create_user(session: AsyncSession, profile: UserProfile | None) -> UserModel | None:
        """Fetch existing user by username or create a new user record."""
        if not profile or not profile.username:
            return None

        stmt = select(UserModel).where(UserModel.username == profile.username)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user is None:
            user = UserModel(
                username=profile.username,
                account_age_days=profile.account_age_days,
                followers=profile.followers,
                following=profile.following,
                posts_per_day=profile.posts_per_day,
                comments_per_day=profile.comments_per_day,
                engagement_rate=profile.engagement_rate,
                duplicate_content_ratio=profile.duplicate_content_ratio,
                hashtag_repetition_rate=profile.hashtag_repetition_rate,
            )
            session.add(user)
            await session.flush()
        else:
            # Update latest behavioural markers
            user.followers = profile.followers
            user.following = profile.following
            if profile.account_age_days is not None:
                user.account_age_days = profile.account_age_days
            if profile.posts_per_day is not None:
                user.posts_per_day = profile.posts_per_day

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
            comment_author = await cls.get_or_create_user(session, c.author)
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

        # 4. Evidence records
        ev_data = module_breakdowns.get("evidence", {})
        fact_checks = ev_data.get("fact_checks", [])
        for fc in fact_checks:
            ev_record = EvidenceModel(
                post_id=post_record.id,
                claim_text=fc.get("claim", ""),
                status=ev_data.get("status", "NO_FACT_CHECK_FOUND"),
                publisher=fc.get("publisher"),
                publisher_url=fc.get("publisher_url"),
                raw_rating=fc.get("raw_rating"),
                normalized_truth_score=fc.get("normalized_truth_score"),
                source_credibility_weight=fc.get("source_credibility"),
                ocr_extracted_text=ev_data.get("ocr_extracted_text"),
            )
            session.add(ev_record)

        # 5. Analysis Result record
        conf_int = analysis_output.get("confidence_interval", [None, None])
        result_record = AnalysisResultModel(
            request_id=request_id,
            post_id=post_record.id,
            final_score=analysis_output["final_score"],
            classification=analysis_output["classification"],
            ai_generated_probability=analysis_output.get("ai_generated_probability"),
            confidence_level=analysis_output.get("confidence_level", "MEDIUM"),
            confidence_interval_low=conf_int[0] if len(conf_int) > 0 else None,
            confidence_interval_high=conf_int[1] if len(conf_int) > 1 else None,
            comment_score=module_breakdowns.get("comments", {}).get("score"),
            evidence_score=module_breakdowns.get("evidence", {}).get("score"),
            behaviour_score=module_breakdowns.get("user_behaviour", {}).get("score"),
            similarity_score=module_breakdowns.get("similarity", {}).get("score"),
            explanation_summary=analysis_output.get("summary_explanation", ""),
            positive_factors=analysis_output.get("positive_factors", []),
            negative_factors=analysis_output.get("negative_factors", []),
            module_breakdowns=module_breakdowns,
            flags=analysis_output.get("flags", []),
        )
        session.add(result_record)
        await session.commit()
        await session.refresh(result_record)

        logger.info("Persisted verification session [%s] for post id %d", request_id, post_record.id)
        return result_record


persistence_service = VerificationPersistenceService()
