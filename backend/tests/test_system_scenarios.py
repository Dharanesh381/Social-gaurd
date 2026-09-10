"""
Comprehensive End-to-End System Test Suite for Social Guard.

Covers all 17 system testing scenarios:
1. Genuine content
2. False content
3. Misleading/recycled content
4. Uncertain/unverified content
5. High comment repetition
6. Abnormal comment burst
7. Anomalous user behaviour
8. Similar older content
9. No Google Fact Check result
10. Fact-check contradiction
11. AI-generated media
12. Missing comments
13. Missing user information
14. Missing media
15. API failure / graceful degradation
16. Database failure resilience
17. Extension / backend connection failure
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.domain_models import (
    CredibilityClassification,
    Comment,
    Media,
    MediaType,
    SocialMediaPost,
    UserProfile,
)
from app.modules.comment_analysis.analyzer import comment_analyzer
from app.modules.evidence_verification.analyzer import evidence_verifier
from app.modules.evidence_verification.factcheck_client import fact_check_client
from app.modules.user_behaviour.analyzer import user_behaviour_analyzer
from app.modules.similar_content.analyzer import similar_content_analyzer
from app.modules.similar_content.content_repository import (
    HistoricalContentItem,
    InMemoryContentRepository,
)
from app.modules.score_fusion.ai_detector import (
    AIGeneratedMediaDetector,
    PerplexityTextAIDetector,
    ai_media_detector,
)
from app.modules.score_fusion.engine import score_fusion_engine
from app.modules.score_fusion.explainability import explainability_engine


client = TestClient(app)


# ------------------------------------------------------------------------------
# 1. Genuine content
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_01_genuine_content():
    """Case 1: Legitimate post by normal user, supported fact check, natural comments."""
    fact_check_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "NASA successfully lands new rover on Mars.",
                "claimant": "NASA",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check", "site": "reuters.com"},
                        "textualRating": "True",
                        "url": "https://reuters.com/factcheck/nasa-mars",
                    }
                ],
            }
        ],
    })

    payload = {
        "post": {
            "platform": "twitter",
            "text": "NASA successfully lands new rover on Mars.",
            "author": {
                "username": "science_reporter",
                "account_age_days": 1800,
                "followers": 45000,
                "following": 800,
                "posts_per_day": 3.2,
                "comments_per_day": 4.0,
                "engagement_rate": 0.045,
                "duplicate_content_ratio": 0.02,
                "hashtag_repetition_rate": 0.05,
            },
            "comments": [
                {
                    "comment_id": f"c_{i}",
                    "text": f"Amazing mission achievement number {i}! 🚀🔭",
                    "likes": 10 + i,
                    "emojis": ["🚀", "🔭"],
                }
                for i in range(8)
            ],
        }
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["consolidated_score"] >= 60.0
    assert data["classification"] in [CredibilityClassification.LIKELY_REAL.value, CredibilityClassification.PROBABLY_REAL.value]


# ------------------------------------------------------------------------------
# 2. False content
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_02_false_content():
    """Case 2: Debunked false hoax with fact check contradiction."""
    fact_check_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "Drinking boiling bleach cures viruses.",
                "claimant": "Social Media",
                "claimReview": [
                    {
                        "publisher": {"name": "Snopes", "site": "snopes.com"},
                        "textualRating": "False / Dangerous Hoax",
                        "url": "https://snopes.com/factcheck/bleach-cure",
                    }
                ],
            }
        ],
    })

    payload = {
        "post": {
            "platform": "facebook",
            "text": "Drinking boiling bleach completely cures all viruses in 5 minutes!",
        }
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["consolidated_score"] < 40.0
    assert data["classification"] in [CredibilityClassification.PROBABLY_FAKE.value, CredibilityClassification.LIKELY_FAKE.value]


# ------------------------------------------------------------------------------
# 3. Misleading/recycled content
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_03_misleading_recycled_content():
    """Case 3: Recycled viral hoax matching older content from years ago."""
    now = datetime.now(timezone.utc)
    res = await similar_content_analyzer.analyze(
        text="Urgent: Governments announce emergency lockdown protocols across all airports due to a mystery virus!",
        hashtags=["#breaking", "#lockdown", "#emergency"],
        post_timestamp=now,
        image_phash_override="f0e1d2c3b4a59687",
    )

    assert res["recycled_content"] is True
    assert res["similarity_score"] < 50.0
    assert "RECYCLED_HISTORICAL_CONTENT_DETECTED" in res["flags"]


# ------------------------------------------------------------------------------
# 4. Uncertain/unverified content
# ------------------------------------------------------------------------------
def test_case_04_uncertain_unverified_content():
    """Case 4: Random obscure statement with no fact-checks and no comment data."""
    fact_check_client.search_claims = AsyncMock(return_value={"status": "NO_FACT_CHECK_FOUND", "claims": []})
    payload = {
        "post": {
            "platform": "reddit",
            "text": "My neighborhood garden produced three extra large pumpkins this autumn.",
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 40.0 <= data["consolidated_score"] <= 75.0
    assert data["classification"] in [CredibilityClassification.UNCERTAIN.value, CredibilityClassification.PROBABLY_REAL.value]


# ------------------------------------------------------------------------------
# 5. High comment repetition (Copypasta Bot Spam)
# ------------------------------------------------------------------------------
def test_case_05_high_comment_repetition():
    """Case 5: Repeated identical copypasta comments indicating coordinated spam."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time),
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time + timedelta(seconds=5)),
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time + timedelta(seconds=10)),
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time + timedelta(seconds=15)),
    ]
    res = comment_analyzer.analyze(comments)
    assert res["comment_score"] < 60.0
    assert res["metrics"]["duplicate_ratio"] >= 0.75
    assert "HIGH_DUPLICATE_COMMENT_RATIO" in res["flags"]


# ------------------------------------------------------------------------------
# 6. Abnormal comment burst
# ------------------------------------------------------------------------------
def test_case_06_abnormal_comment_burst():
    """Case 6: Unnatural flood of comments arriving within the same few seconds."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(
            text=f"Spam link click here {i}",
            timestamp=base_time + timedelta(seconds=i * 2),
        )
        for i in range(20)
    ]
    res = comment_analyzer.analyze(comments)
    assert res["metrics"]["temporal_anomaly_score"] > 0
    assert "TEMPORAL_BURST_ACTIVITY_DETECTED" in res["flags"]


# ------------------------------------------------------------------------------
# 7. Anomalous user behaviour
# ------------------------------------------------------------------------------
def test_case_07_anomalous_user_behaviour():
    """Case 7: Brand new account exhibiting hyperactive automated bot velocity."""
    bot_profile = UserProfile(
        username="auto_blast_009",
        account_age_days=1,
        followers=2,
        following=4900,
        posts_per_day=450.0,
        comments_per_day=900.0,
        average_posting_interval_seconds=60.0,
        engagement_rate=0.0001,
        duplicate_content_ratio=0.98,
        hashtag_repetition_rate=0.95,
    )
    res = user_behaviour_analyzer.analyze(bot_profile)
    assert res["behaviour_score"] < 50.0
    assert res["anomaly_score"] > 0.50
    assert "NEW_ACCOUNT_HIGH_POSTING_VELOCITY" in res["flags"]


# ------------------------------------------------------------------------------
# 8. Similar older content
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_08_similar_older_content():
    """Case 8: Semantic match with older existing post in repository."""
    res = await similar_content_analyzer.analyze(
        text="NASA rovers detect liquid water beneath Martian polar ice caps in deep radar soundings.",
        hashtags=["#space", "#mars", "#nasa"],
    )
    assert res["similar_content_count"] >= 1
    assert res["text_similarity"] > 0.80


# ------------------------------------------------------------------------------
# 9. No Google Fact Check result (Neutral Baseline)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_09_no_google_fact_check_result():
    """Case 9: Fact check returns 0 claims -> Must return 50.0 neutral fallback."""
    fact_check_client.search_claims = AsyncMock(return_value={"status": "NO_FACT_CHECK_FOUND", "claims": []})
    res = await evidence_verifier.verify("New local bakery opens in downtown.")
    assert res["evidence_score"] == 50.0
    assert res["status"] == "NO_FACT_CHECK_FOUND"


# ------------------------------------------------------------------------------
# 10. Fact-check contradiction
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_10_fact_check_contradiction():
    """Case 10: Official fact-checker clearly debunks claim as false."""
    fact_check_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "The Eiffel Tower was destroyed in a meteor strike.",
                "claimant": "Social Post",
                "claimReview": [
                    {
                        "publisher": {"name": "AFP Fact Check", "site": "afp.com"},
                        "textualRating": "Pants on Fire / False",
                        "url": "https://factcheck.afp.com/eiffel-tower-meteor",
                    }
                ],
            }
        ],
    })
    res = await evidence_verifier.verify("The Eiffel Tower was destroyed in a meteor strike.")
    assert res["evidence_score"] == 0.0
    assert res["status"] == "CONTRADICTED"
    assert "DEBUNKED_BY_FACT_CHECKERS" in res["flags"]


# ------------------------------------------------------------------------------
# 11. AI-generated media
# ------------------------------------------------------------------------------
def test_case_11_ai_generated_media():
    """Case 11: Text detector analyzes uniform/synthetic text for AI likelihood."""
    ai_text = (
        "Furthermore, it is important to remember that comprehensive analysis "
        "indicates that artificial intelligence presents multifaceted paradigms. "
        "Consequently, one must take into consideration all relevant factors."
    )
    res = ai_media_detector.analyze_text(ai_text)
    assert res["ai_generation_probability"] is not None
    assert 0.0 <= res["ai_generation_probability"] <= 100.0
    assert res["status"] == "ANALYZED"


# ------------------------------------------------------------------------------
# 12. Missing comments (Graceful handling)
# ------------------------------------------------------------------------------
def test_case_12_missing_comments():
    """Case 12: Empty comments list returns neutral 50.0 without crashing."""
    res = comment_analyzer.analyze([])
    assert res["comment_score"] == 50.0
    assert res["metrics"]["comment_count"] == 0
    assert "NO_COMMENTS_AVAILABLE" in res["flags"]


# ------------------------------------------------------------------------------
# 13. Missing user information (Graceful imputation)
# ------------------------------------------------------------------------------
def test_case_13_missing_user_information():
    """Case 13: None UserProfile returns neutral baseline 50.0."""
    res = user_behaviour_analyzer.analyze(None)
    assert res["behaviour_score"] == 50.0
    assert "USER_METADATA_UNAVAILABLE" in res["flags"]


# ------------------------------------------------------------------------------
# 14. Missing media (Graceful handling)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_14_missing_media():
    """Case 14: Analyzing empty media list returns graceful status without failing request."""
    res = await ai_media_detector.analyze_media_url("")
    assert res["status"] == "EMPTY_URL"
    assert res["ai_generation_probability"] is None


# ------------------------------------------------------------------------------
# 15. API failure / graceful degradation
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_case_15_api_failure_graceful_degradation():
    """Case 15: External Fact-Check API throws network error -> Fall back to neutral score."""
    fact_check_client.search_claims = AsyncMock(return_value={"status": "RATE_LIMITED", "claims": []})
    res = await evidence_verifier.verify("Some breaking political event occurred.")
    assert res["evidence_score"] == 50.0
    assert res["status"] == "NO_FACT_CHECK_FOUND"
    assert "FACT_CHECK_API_RATE_LIMITED" in res["flags"]


# ------------------------------------------------------------------------------
# 16. Database failure resilience
# ------------------------------------------------------------------------------
def test_case_16_database_failure_resilience():
    """Case 16: Database persistence failure does NOT crash the /analyze API response."""
    payload = {
        "post": {
            "platform": "reddit",
            "text": "A simple test post to ensure database failure isolation.",
        }
    }
    with patch("app.services.persistence.VerificationPersistenceService.save_verification_session", new=AsyncMock(side_effect=Exception("Database lock/offline error"))):
        response = client.post("/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "consolidated_score" in data
        assert "classification" in data


# ------------------------------------------------------------------------------
# 17. Extension / Backend connection failure simulation
# ------------------------------------------------------------------------------
def test_case_17_extension_backend_invalid_payload_error_contract():
    """Case 17: Malformed or unprocessable payload returns standard HTTP 422 with actionable error detail."""
    response = client.post("/analyze", json={"bad_key": "invalid_structure"})
    assert response.status_code in [422, 400]
    data = response.json()
    assert "error" in data or "detail" in data or "message" in data
