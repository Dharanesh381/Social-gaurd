"""Tests for automated author extraction, enrichment, and schema normalization."""

import pytest
from app.modules.user_behaviour.analyzer import UserBehaviourAnalyzer
from app.platform.author_resolver import (
    extract_username_from_url,
    infer_platform_author_heuristics,
    resolve_and_enrich_author,
)
from app.schemas.domain_models import (
    AnalysisRequest,
    SocialMediaPost,
    UserProfile,
)
from app.services.orchestrator import AnalysisOrchestratorService


def test_extract_username_from_url():
    """Verify URL regex extracts handles across platforms accurately."""
    # Twitter / X
    user, platform = extract_username_from_url("https://x.com/tech_insider/status/18492048201")
    assert user == "tech_insider"
    assert platform == "twitter"

    user, platform = extract_username_from_url("https://twitter.com/science_digest/status/999111")
    assert user == "science_digest"
    assert platform == "twitter"

    # Reserved routes should not be extracted as user handles
    user, platform = extract_username_from_url("https://x.com/explore")
    assert user is None
    assert platform == "twitter"

    # Reddit
    user, platform = extract_username_from_url("https://www.reddit.com/user/space_physicist/comments/")
    assert user == "space_physicist"
    assert platform == "reddit"

    user, platform = extract_username_from_url("https://reddit.com/r/technology/comments/123/future_ai/")
    assert user is None
    assert platform == "reddit"

    # Instagram
    user, platform = extract_username_from_url("https://www.instagram.com/nature_photography/p/DB12345/")
    assert user == "nature_photography"
    assert platform == "instagram"


def test_user_profile_alias_normalization():
    """Verify UserProfile model_validator maps legacy and alternative field names."""
    payload = {
        "username": "alias_tester",
        "followers_count": 1250,
        "following_count": 340,
        "recent_posts_frequency_per_day": 4.5,
        "recent_comments_frequency_per_day": 6.2,
        "duplicate_posts_ratio": 0.08,
        "average_engagement_rate": 0.05,
    }
    profile = UserProfile.model_validate(payload)
    assert profile.username == "alias_tester"
    assert profile.followers == 1250
    assert profile.following == 340
    assert profile.posts_per_day == 4.5
    assert profile.comments_per_day == 6.2
    assert profile.duplicate_content_ratio == 0.08
    assert profile.engagement_rate == 0.05


def test_infer_platform_author_heuristics():
    """Verify grounded behavioral heuristics separate bot patterns from organic users."""
    # Bot handle pattern
    bot_heuristics = infer_platform_author_heuristics("crypto_deals_849281", "twitter")
    assert bot_heuristics["account_age_days"] < 30
    assert bot_heuristics["following"] > 2000
    assert bot_heuristics["duplicate_content_ratio"] > 0.50

    # Organic handle
    organic_heuristics = infer_platform_author_heuristics("climate_scientist", "twitter")
    assert organic_heuristics["account_age_days"] >= 365
    assert organic_heuristics["follower_following_ratio"] if "follower_following_ratio" in organic_heuristics else True
    assert organic_heuristics["duplicate_content_ratio"] < 0.10


@pytest.mark.asyncio
async def test_resolve_and_enrich_author_live_twitter_url():
    """Verify live Twitter post URL enriches author and runs Module 3 successfully."""
    author = await resolve_and_enrich_author(
        author=None,
        post_url="https://x.com/astro_insider/status/19284719284",
        platform="twitter",
    )
    assert author is not None
    assert author.username == "astro_insider"
    assert author.followers > 0
    assert author.account_age_days is not None

    analyzer = UserBehaviourAnalyzer()
    result = analyzer.analyze(author)
    assert result["status"] == "COMPLETED"
    assert result["score"] >= 70.0
    assert result["is_anomalous"] is False
    assert "astro_insider" in result["explanation"]


@pytest.mark.asyncio
async def test_orchestrator_enrichment_from_post_url():
    """Verify end-to-end orchestrator enriches post.author from post_url and evaluates Module 3."""
    orchestrator = AnalysisOrchestratorService()

    req = AnalysisRequest(
        post=SocialMediaPost(
            platform="twitter",
            post_url="https://x.com/daily_health_brief/status/123456789",
            text="Recent biomedical studies report preliminary findings on cellular regeneration.",
            author=None,  # No author provided, only post_url
            comments=[],
        )
    )

    result = await orchestrator.analyze_post(req)

    # Post info should retain post_url and resolved author
    assert result.post_info.get("post_url") == "https://x.com/daily_health_brief/status/123456789"
    assert result.post_info.get("has_author_metadata") is True
    assert result.post_info.get("author_username") == "daily_health_brief"

    # Module 3 should be completed with non-neutral score
    m3 = result.module_3
    assert m3["status"] == "COMPLETED"
    assert m3["score"] is not None
    assert m3["metrics"].get("account_age_days") is not None
    assert "daily_health_brief" in m3["explanation"]

