"""Unit tests for Module 3: User Behaviour Analysis Engine."""

import math
import pytest

from app.modules.user_behaviour.analyzer import UserBehaviourAnalyzer
from app.modules.user_behaviour.anomaly_detector import UserAnomalyDetector
from app.modules.user_behaviour.feature_extractor import (
    extract_user_features,
    vectorize_features,
)
from app.schemas.domain_models import UserProfile


# ==============================================================================
# 1. FEATURE EXTRACTION & IMPUTATION TESTS
# ==============================================================================

def test_extract_user_features_full():
    """Test extraction with all attributes provided."""
    profile = UserProfile(
        username="authentic_journalist",
        account_age_days=1200,
        followers=5400,
        following=800,
        posts_per_day=3.5,
        comments_per_day=5.0,
        average_posting_interval_seconds=14000.0,
        engagement_rate=0.045,
        duplicate_content_ratio=0.02,
        hashtag_repetition_rate=0.15,
    )
    features = extract_user_features(profile)
    assert features["account_age_days"] == 1200.0
    assert features["followers"] == 5400.0
    assert features["follower_following_ratio"] == round(5400.0 / 800.0, 4)
    assert features["duplicate_content_ratio"] == 0.02
    assert features["average_posting_interval_seconds"] == 14000.0


def test_extract_user_features_imputes_missing_values():
    """Test fallback imputation for partial profiles."""
    profile = UserProfile(
        username="minimal_user",
        followers=100,
        following=50,
    )
    features = extract_user_features(profile)
    assert features["followers"] == 100.0
    assert features["following"] == 50.0
    assert features["account_age_days"] == 365.0  # Default imputed
    assert features["posts_per_day"] == 2.0  # Default imputed
    assert features["duplicate_content_ratio"] == 0.05


def test_vectorize_features_log_scaling():
    """Test log scaling handles power-law counts safely without overflow."""
    sample = {
        "account_age_days": 1000.0,
        "followers": 1_000_000.0,
        "following": 500.0,
        "follower_following_ratio": 2000.0,
        "posts_per_day": 5.0,
        "comments_per_day": 10.0,
        "average_posting_interval_seconds": 15000.0,
        "engagement_rate": 0.03,
        "duplicate_content_ratio": 0.05,
        "hashtag_repetition_rate": 0.10,
    }
    vec = vectorize_features(sample)
    assert len(vec) == 10
    # Followers vector value should be log1p(1,000,000) ~ 13.81
    assert math.isclose(vec[1], math.log1p(1_000_000.0), rel_tol=1e-3)
    assert not any(math.isnan(x) or math.isinf(x) for x in vec)


# ==============================================================================
# 2. REQUIRED MODULE 3 SCENARIO TESTS
# ==============================================================================

@pytest.fixture
def analyzer():
    return UserBehaviourAnalyzer()


def test_normal_mature_account(analyzer: UserBehaviourAnalyzer):
    """1. Normal mature account: balanced engagement, low duplication -> High score & is_anomalous=False."""
    profile = UserProfile(
        username="dr_astronomer",
        account_age_days=1500,
        followers=8500,
        following=620,
        posts_per_day=1.8,
        comments_per_day=3.2,
        average_posting_interval_seconds=30000.0,
        engagement_rate=0.04,
        duplicate_content_ratio=0.01,
        hashtag_repetition_rate=0.08,
    )
    result = analyzer.analyze(profile)

    assert result["score"] >= 80.0
    assert result["behaviour_score"] == result["score"]
    assert result["anomaly_score"] < 0.45
    assert result["is_anomalous"] is False
    assert len(result["flags"]) == 0
    assert "mature, balanced engagement" in result["explanation"]
    assert result["status"] == "COMPLETED"


def test_high_activity_account(analyzer: UserBehaviourAnalyzer):
    """2. High-activity account: active journalist or creator -> Organic volume, not penalized as a bot."""
    profile = UserProfile(
        username="reuters_wire_anchor",
        account_age_days=2200,
        followers=45000,
        following=1100,
        posts_per_day=14.0,  # High activity
        comments_per_day=22.0,
        average_posting_interval_seconds=4500.0,
        engagement_rate=0.048,
        duplicate_content_ratio=0.02,  # Organic content, not spam
        hashtag_repetition_rate=0.15,
    )
    result = analyzer.analyze(profile)

    assert result["score"] >= 70.0  # Maintained healthy score
    assert result["is_anomalous"] is False
    assert "NEW_ACCOUNT_HIGH_POSTING_VELOCITY" not in result["flags"]
    assert "HIGH_TIMELINE_DUPLICATION_RATIO" not in result["flags"]
    assert "EXCESSIVE_HASHTAG_REPETITION" not in result["flags"]


def test_suspicious_repetitive_account(analyzer: UserBehaviourAnalyzer):
    """3. Suspicious repetitive account: high duplicate content & velocity -> Penalized & is_anomalous=True."""
    profile = UserProfile(
        username="crypto_airdrop_blast",
        account_age_days=45,
        followers=250,
        following=3500,
        posts_per_day=75.0,  # Extreme velocity
        comments_per_day=90.0,
        average_posting_interval_seconds=50.0,
        engagement_rate=0.002,
        duplicate_content_ratio=0.85,  # Heavy duplication
        hashtag_repetition_rate=0.80,  # Heavy hashtag repetition
    )
    result = analyzer.analyze(profile)

    assert result["score"] < 50.0
    assert result["is_anomalous"] is True
    assert result["anomaly_score"] > 0.55
    assert "HIGH_TIMELINE_DUPLICATION_RATIO" in result["flags"]
    assert "EXCESSIVE_HASHTAG_REPETITION" in result["flags"]
    assert "EXTREME_POSTING_VELOCITY" in result["flags"]
    assert "ANOMALOUS_BEHAVIOURAL_PATTERN" in result["flags"]
    # CRITICAL RULE check: Anomaly explanation must state that anomaly does not mean content is fake
    assert "does NOT directly mean that the content is fake" in result["explanation"]


def test_new_account(analyzer: UserBehaviourAnalyzer):
    """4. New account: fresh account with aggressive velocity -> Flagged with guardrail."""
    profile = UserProfile(
        username="fast_pump_deals",
        account_age_days=2,
        followers=8,
        following=1500,
        posts_per_day=35.0,
        comments_per_day=20.0,
        duplicate_content_ratio=0.25,
        hashtag_repetition_rate=0.30,
    )
    result = analyzer.analyze(profile)

    assert result["score"] < 65.0
    assert "NEW_ACCOUNT_HIGH_POSTING_VELOCITY" in result["flags"]


def test_missing_fields(analyzer: UserBehaviourAnalyzer):
    """5. Missing fields: graceful imputation without error and neutral baseline for None."""
    # Sub-case A: Partial profile with missing fields
    partial_profile = UserProfile(
        username="partial_info_user",
        followers=350,
        following=200,
    )
    result_partial = analyzer.analyze(partial_profile)
    assert 0.0 <= result_partial["score"] <= 100.0
    assert 0.0 <= result_partial["anomaly_score"] <= 1.0
    assert isinstance(result_partial["is_anomalous"], bool)
    assert result_partial["metrics"]["followers"] == 350.0
    assert result_partial["metrics"]["account_age_days"] == 365.0  # Imputed default
    assert result_partial["status"] == "COMPLETED"

    # Sub-case B: None profile
    result_none = analyzer.analyze(None)
    assert result_none["score"] == 50.0  # Neutral baseline
    assert result_none["behaviour_score"] == 50.0
    assert result_none["anomaly_score"] == 0.0
    assert result_none["is_anomalous"] is False
    assert "USER_METADATA_UNAVAILABLE" in result_none["flags"]
    assert result_none["status"] == "USER_METADATA_UNAVAILABLE"


def test_extreme_values(analyzer: UserBehaviourAnalyzer):
    """6. Extreme values: massive numbers handled stably without NaN or mathematical overflow."""
    profile = UserProfile(
        username="hyper_bot_extreme",
        account_age_days=1,
        followers=50_000_000,
        following=2_000_000,
        posts_per_day=5000.0,
        comments_per_day=10000.0,
        average_posting_interval_seconds=0.05,
        engagement_rate=0.0001,
        duplicate_content_ratio=1.0,
        hashtag_repetition_rate=1.0,
    )
    result = analyzer.analyze(profile)

    assert 0.0 <= result["score"] <= 100.0
    assert 0.0 <= result["anomaly_score"] <= 1.0
    assert result["is_anomalous"] is True
    # Z-scores computed properly
    assert result["metrics"]["posts_per_day_zscore"] > 10.0
    assert result["metrics"]["posts_per_day_iqr_outlier"] == 1.0
    assert not math.isnan(result["score"])
    assert not math.isinf(result["score"])
    assert "does NOT directly mean that the content is fake" in result["explanation"]
