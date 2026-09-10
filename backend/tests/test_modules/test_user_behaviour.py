"""Unit tests for Module 3: User Behaviour Analysis Engine."""

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


# ==============================================================================
# 2. ISOLATION FOREST & STATISTICAL TESTS
# ==============================================================================

def test_anomaly_detector_normal_vs_extreme_bot():
    """Test Isolation Forest differentiates standard organic user from high-frequency bot."""
    detector = UserAnomalyDetector(contamination=0.08, n_estimators=80, random_state=42)

    # Standard organic profile
    normal_profile = {
        "account_age_days": 800.0,
        "followers": 450.0,
        "following": 350.0,
        "follower_following_ratio": 1.28,
        "posts_per_day": 2.2,
        "comments_per_day": 4.0,
        "average_posting_interval_seconds": 25000.0,
        "engagement_rate": 0.035,
        "duplicate_content_ratio": 0.03,
        "hashtag_repetition_rate": 0.10,
    }
    is_ano_norm, raw_norm, score_norm = detector.predict_anomaly(normal_profile)
    assert is_ano_norm is False
    assert raw_norm > 0.0  # Decision function positive for normal
    assert score_norm < 0.50

    # Extreme automated spam profile (1 day old, 300 posts/day, 90% duplicate ratio)
    extreme_bot = {
        "account_age_days": 1.0,
        "followers": 5.0,
        "following": 4000.0,
        "follower_following_ratio": 0.001,
        "posts_per_day": 300.0,
        "comments_per_day": 500.0,
        "average_posting_interval_seconds": 10.0,
        "engagement_rate": 0.0001,
        "duplicate_content_ratio": 0.95,
        "hashtag_repetition_rate": 0.90,
    }
    is_ano_bot, raw_bot, score_bot = detector.predict_anomaly(extreme_bot)
    assert is_ano_bot is True
    assert raw_bot < 0.0  # Decision function negative for anomaly
    assert score_bot > 0.60


def test_statistical_zscore_and_iqr_outliers():
    """Test Z-score and IQR calculation on extreme velocity."""
    detector = UserAnomalyDetector()
    features = {
        "posts_per_day": 60.0,  # Far above population mean (2.5)
        "duplicate_content_ratio": 0.85,  # Far above mean (0.05)
    }
    stat_metrics = detector.compute_statistical_anomalies(features)
    assert stat_metrics["posts_per_day_zscore"] > 5.0
    assert stat_metrics["posts_per_day_iqr_outlier"] == 1.0
    assert stat_metrics["duplicate_content_ratio_iqr_outlier"] == 1.0


# ==============================================================================
# 3. FULL USER BEHAVIOUR ANALYZER TESTS
# ==============================================================================

@pytest.fixture
def analyzer():
    return UserBehaviourAnalyzer()


def test_none_profile_returns_neutral_baseline(analyzer: UserBehaviourAnalyzer):
    """Test None user profile returns neutral 50.0 baseline."""
    result = analyzer.analyze(None)
    assert result["behaviour_score"] == 50.0
    assert result["anomaly_score"] == 0.0
    assert "USER_METADATA_UNAVAILABLE" in result["flags"]
    assert "neutral baseline" in result["explanation"]


def test_legitimate_user_high_score(analyzer: UserBehaviourAnalyzer):
    """Test established user with organic activity gets high behaviour score."""
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
    assert result["behaviour_score"] >= 80.0
    assert result["anomaly_score"] < 0.40
    assert len(result["flags"]) == 0
    assert "exhibits mature, balanced engagement" in result["explanation"]


def test_new_account_spam_bot_penalized(analyzer: UserBehaviourAnalyzer):
    """Test new account with extreme posting velocity is penalized with appropriate flags."""
    profile = UserProfile(
        username="fast_crypto_deals",
        account_age_days=2,
        followers=10,
        following=2500,
        posts_per_day=80.0,
        comments_per_day=120.0,
        average_posting_interval_seconds=60.0,
        engagement_rate=0.001,
        duplicate_content_ratio=0.75,
        hashtag_repetition_rate=0.85,
    )
    result = analyzer.analyze(profile)
    assert result["behaviour_score"] < 50.0
    assert result["anomaly_score"] > 0.60
    assert "NEW_ACCOUNT_HIGH_POSTING_VELOCITY" in result["flags"]
    assert "HIGH_TIMELINE_DUPLICATION_RATIO" in result["flags"]
    assert "EXCESSIVE_HASHTAG_REPETITION" in result["flags"]
    assert "does not prove post is fake" in result["explanation"]
