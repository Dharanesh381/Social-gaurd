"""Unit tests for Social Guard Pydantic domain models and validation."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.domain_models import (
    AnalysisRequest,
    BehaviourAnalysisResult,
    Comment,
    CommentAnalysisResult,
    CredibilityClassification,
    EvidenceAnalysisResult,
    EvidenceVerificationState,
    FactCheckMatch,
    FinalAnalysisResult,
    Media,
    MediaType,
    ScoreFusionResult,
    SimilarContentResult,
    SocialMediaPost,
    UserProfile,
)


# ==============================================================================
# 1. INPUT MODELS TESTS
# ==============================================================================

def test_media_model_valid():
    """Test valid Media model creation with defaults and custom attributes."""
    media = Media(
        url="https://example.com/photo.jpg",
        media_type=MediaType.IMAGE,
        ocr_extracted_text="Sample text in image",
        perceptual_hash="d8f1e2c3b4a59687",
    )
    assert str(media.url) == "https://example.com/photo.jpg"
    assert media.media_type == MediaType.IMAGE
    assert media.ocr_extracted_text == "Sample text in image"
    assert media.perceptual_hash == "d8f1e2c3b4a59687"


def test_media_model_invalid_url():
    """Test Media model fails on invalid URL format."""
    with pytest.raises(ValidationError):
        Media(url="not-a-valid-http-url")


def test_user_profile_valid_and_bounds():
    """Test UserProfile model with valid data and metric ranges."""
    profile = UserProfile(
        username="fact_checker_99",
        account_age_days=365,
        followers=1200,
        following=300,
        posts_per_day=4.2,
        comments_per_day=1.5,
        average_posting_interval_seconds=3600.0,
        engagement_rate=0.045,
        duplicate_content_ratio=0.10,
        hashtag_repetition_rate=0.25,
    )
    assert profile.username == "fact_checker_99"
    assert profile.followers == 1200
    assert profile.posts_per_day == 4.2
    assert profile.duplicate_content_ratio == 0.10


def test_user_profile_invalid_ratios():
    """Test UserProfile raises validation errors on negative or out-of-bound ratios."""
    with pytest.raises(ValidationError):
        # duplicate_content_ratio must be <= 1.0
        UserProfile(username="bad_user", duplicate_content_ratio=1.5)

    with pytest.raises(ValidationError):
        # followers must be >= 0
        UserProfile(username="bad_user", followers=-5)


def test_comment_model_and_emoji_auto_count():
    """Test Comment model and automated emoji count calculation."""
    comment = Comment(
        text="This is shocking! 🚨👀",
        emojis=["🚨", "👀"],
        likes=10,
    )
    assert comment.text == "This is shocking! 🚨👀"
    assert comment.emoji_count == 2
    assert comment.likes == 10


def test_comment_empty_text_fails():
    """Test Comment model rejects empty strings."""
    with pytest.raises(ValidationError):
        Comment(text="")


def test_social_media_post_normalization_and_hashtags():
    """Test SocialMediaPost normalizes platform strings and formats hashtags."""
    post = SocialMediaPost(
        platform="  TWITTER  ",
        text="Breaking report on atmospheric sensor readings.",
        hashtags=["science", "#Mars", "spaceNews "],
        media=[Media(url="https://example.com/chart.png")],
        author=UserProfile(username="lead_reporter", followers=5000),
        comments=[Comment(text="Interesting findings!")],
    )
    assert post.platform == "twitter"
    assert post.hashtags == ["#science", "#Mars", "#spaceNews"]
    assert len(post.media) == 1
    assert len(post.comments) == 1
    assert post.author.username == "lead_reporter"


def test_analysis_request_valid():
    """Test top-level AnalysisRequest model."""
    post = SocialMediaPost(
        text="A factual statement for testing.",
    )
    request = AnalysisRequest(
        request_id="req_001",
        post=post,
        custom_weights={"comment_analysis": 0.2, "evidence_verification": 0.4},
    )
    assert request.request_id == "req_001"
    assert request.post.text == "A factual statement for testing."
    assert request.custom_weights["comment_analysis"] == 0.2


# ==============================================================================
# 2. MODULE RESULT MODELS TESTS
# ==============================================================================

def test_comment_analysis_result():
    """Test Module 1 CommentAnalysisResult schema."""
    result = CommentAnalysisResult(
        score=75.5,
        total_comments_analyzed=20,
        duplicate_comment_ratio=0.05,
        semantic_similarity_mean=0.35,
        emoji_entropy=2.41,
        temporal_burst_zscore=1.1,
        temporal_burst_detected=False,
        abnormal_comment_activity=False,
        intermediate_metrics={"clusters_count": 3},
    )
    assert result.module_name == "comment_analysis"
    assert result.score == 75.5
    assert result.duplicate_comment_ratio == 0.05
    assert result.intermediate_metrics["clusters_count"] == 3


def test_evidence_analysis_result_with_fact_checks():
    """Test Module 2 EvidenceAnalysisResult schema with fact-check matches."""
    match = FactCheckMatch(
        claim="Liquid water was found on Mars yesterday.",
        claimant="Viral Post",
        publisher="Reuters Fact Check",
        publisher_url="https://reuters.com/factcheck/123",
        review_rating="False",
        normalized_score=0.0,
    )
    result = EvidenceAnalysisResult(
        score=15.0,
        state=EvidenceVerificationState.CONTRADICTED,
        extracted_claims=["Liquid water was found on Mars yesterday."],
        matched_fact_checks=[match],
        source_credibility_score=0.95,
        ocr_extracted_text="Text inside meme",
    )
    assert result.module_name == "evidence_verification"
    assert result.state == EvidenceVerificationState.CONTRADICTED
    assert len(result.matched_fact_checks) == 1
    assert result.matched_fact_checks[0].publisher == "Reuters Fact Check"


def test_behaviour_analysis_result():
    """Test Module 3 BehaviourAnalysisResult schema."""
    result = BehaviourAnalysisResult(
        score=65.0,
        is_anomalous=False,
        isolation_forest_score=-0.12,
        follower_following_ratio=2.5,
        posting_velocity_zscore=0.8,
        engagement_rate=0.03,
        rule_penalties_applied=["new_account_penalty"],
    )
    assert result.module_name == "user_behaviour"
    assert result.is_anomalous is False
    assert result.follower_following_ratio == 2.5


def test_similar_content_result():
    """Test Module 4 SimilarContentResult schema."""
    result = SimilarContentResult(
        score=85.0,
        semantic_similarity_max=0.42,
        perceptual_hash_matches_count=0,
        min_hamming_distance=18,
        recycled_content_detected=False,
        hashtag_coordination_score=0.1,
    )
    assert result.module_name == "similar_content"
    assert result.recycled_content_detected is False
    assert result.min_hamming_distance == 18


# ==============================================================================
# 3. SCORE FUSION & FINAL ANALYSIS RESULT TESTS
# ==============================================================================

def test_score_fusion_result():
    """Test Module 5 ScoreFusionResult schema."""
    weights = {
        "comment_analysis": 0.20,
        "evidence_verification": 0.40,
        "user_behaviour": 0.15,
        "similar_content": 0.25,
    }
    fusion = ScoreFusionResult(
        consolidated_score=82.5,
        classification=CredibilityClassification.LIKELY_REAL,
        weights_applied=weights,
    )
    assert fusion.consolidated_score == 82.5
    assert fusion.classification == CredibilityClassification.LIKELY_REAL


def test_final_analysis_result():
    """Test top-level FinalAnalysisResult consolidated output model."""
    final_res = FinalAnalysisResult(
        request_id="session_xyz_789",
        consolidated_score=78.0,
        classification=CredibilityClassification.PROBABLY_REAL,
        ai_generation_probability=0.15,
        explanation="The post shows consistent factual backing with minor comment disagreement.",
        module_scores={
            "comment_analysis": 72.0,
            "evidence_verification": 85.0,
            "user_behaviour": 70.0,
            "similar_content": 80.0,
        },
        module_results={
            "comment_analysis": {"duplicate_ratio": 0.02},
            "evidence_verification": {"state": "SUPPORTED"},
        },
    )
    assert final_res.request_id == "session_xyz_789"
    assert final_res.consolidated_score == 78.0
    assert final_res.classification == CredibilityClassification.PROBABLY_REAL
    assert final_res.ai_generation_probability == 0.15
    assert "consistent factual backing" in final_res.explanation
    assert final_res.module_scores["evidence_verification"] == 85.0
