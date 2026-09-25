"""Unit and integration tests for PostgreSQL/SQLAlchemy Database Integration."""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.models import (
    AnalysisResultModel,
    Base,
    CommentModel,
    EvidenceModel,
    PostModel,
    UserModel,
)
from app.schemas.domain_models import Comment, Media, SocialMediaPost, UserProfile
from app.services.persistence import VerificationPersistenceService





@pytest.mark.asyncio
async def test_user_creation_and_retrieval(async_db_session: AsyncSession):
    """Test creating and retrieving a user model."""
    user = UserModel(
        username="lead_factchecker",
        account_age_days=500,
        followers=2400,
        following=350,
        posts_per_day=3.2,
    )
    async_db_session.add(user)
    await async_db_session.commit()

    stmt = select(UserModel).where(UserModel.username == "lead_factchecker")
    res = await async_db_session.execute(stmt)
    saved = res.scalar_one()

    assert saved.id is not None
    assert saved.username == "lead_factchecker"
    assert saved.followers == 2400


@pytest.mark.asyncio
async def test_relational_post_comments_and_results(async_db_session: AsyncSession):
    """Test relational integrity across posts, comments, evidence, and analysis results."""
    # 1. User
    user = UserModel(username="news_outlet_01", followers=50000)
    async_db_session.add(user)
    await async_db_session.flush()

    # 2. Post
    post = PostModel(
        platform="twitter",
        text="Official announcement of Mars rover sample cache retrieval.",
        hashtags=["#Mars", "#NASA"],
        media_urls=["https://example.com/mars_rover.jpg"],
        author_id=user.id,
    )
    async_db_session.add(post)
    await async_db_session.flush()

    # 3. Comment
    comment = CommentModel(
        post_id=post.id,
        author_id=user.id,
        text="Historic achievement for planetary science! 🚀",
        emojis=["🚀"],
        emoji_count=1,
    )
    async_db_session.add(comment)

    # 4. Evidence
    evidence = EvidenceModel(
        post_id=post.id,
        claim_text="Mars rover sample cache retrieval",
        status="SUPPORTED",
        publisher="Reuters Fact Check",
        normalized_truth_score=1.0,
        source_credibility_weight=0.98,
    )
    async_db_session.add(evidence)

    # 5. Analysis Result
    result = AnalysisResultModel(
        request_id="sg_req_unit_test_99",
        post_id=post.id,
        final_score=88.5,
        classification="LIKELY REAL",
        ai_generated_probability=0.08,
        confidence_level="HIGH",
        comment_score=80.0,
        evidence_score=98.0,
        behaviour_score=85.0,
        similarity_score=82.0,
        explanation_summary="Content is verified by Reuters Fact Check and supported by healthy discussion.",
        positive_factors=[{"factor": "Evidence verified by Reuters"}],
        negative_factors=[],
    )
    async_db_session.add(result)
    await async_db_session.commit()

    # Verify query with relationships
    stmt = select(PostModel).where(PostModel.id == post.id)
    res = await async_db_session.execute(stmt)
    fetched_post = res.scalar_one()

    assert fetched_post.text == "Official announcement of Mars rover sample cache retrieval."
    assert fetched_post.author.username == "news_outlet_01"


@pytest.mark.asyncio
async def test_persistence_service_end_to_end(async_db_session: AsyncSession):
    """Test VerificationPersistenceService.save_verification_session."""
    post_dto = SocialMediaPost(
        platform="reddit",
        text="Scientists successfully sequence ancient mammalia genome.",
        hashtags=["#Genetics", "#Science"],
        media=[Media(url="https://example.com/mammoth.png")],
        author=UserProfile(username="dna_researcher", followers=1200),
        comments=[Comment(text="Incredible research! Link to the paper?")],
    )

    analysis_output = {
        "final_score": 84.5,
        "classification": "LIKELY REAL",
        "ai_generated_probability": 0.12,
        "confidence_level": "HIGH",
        "confidence_interval": [81.0, 88.0],
        "summary_explanation": "Strong evidence and mature author profile.",
        "positive_factors": [{"factor": "Accredited journal peer review"}],
        "negative_factors": [],
        "flags": [],
    }

    module_breakdowns = {
        "comments": {"score": 78.0},
        "evidence": {
            "score": 90.0,
            "status": "SUPPORTED",
            "fact_checks": [{
                "claim": "Ancient mammalia genome sequenced",
                "publisher": "Science Direct",
                "publisher_url": "https://example.com",
                "raw_rating": "True",
                "normalized_truth_score": 1.0,
                "source_credibility": 0.95,
            }],
        },
        "user_behaviour": {"score": 80.0},
        "similarity": {"score": 85.0},
    }

    saved_record = await VerificationPersistenceService.save_verification_session(
        session=async_db_session,
        request_id="sg_req_test_persistence_101",
        post_data=post_dto,
        analysis_output=analysis_output,
        module_breakdowns=module_breakdowns,
    )

    assert saved_record.id is not None
    assert saved_record.request_id == "sg_req_test_persistence_101"
    assert saved_record.final_score == 84.5
    assert saved_record.classification == "LIKELY REAL"
    assert saved_record.evidence_score == 90.0
