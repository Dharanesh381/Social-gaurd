"""Feature extraction and normalization for user behavioural analysis."""

import math

import numpy as np

from app.schemas.domain_models import UserProfile

# Canonical feature ordering used across model training and inference
FEATURE_NAMES: list[str] = [
    "account_age_days",
    "followers",
    "following",
    "follower_following_ratio",
    "posts_per_day",
    "comments_per_day",
    "average_posting_interval_seconds",
    "engagement_rate",
    "duplicate_content_ratio",
    "hashtag_repetition_rate",
]

# Baseline medians and scaling parameters for robust normalization
FEATURE_DEFAULTS: dict[str, float] = {
    "account_age_days": 365.0,
    "followers": 250.0,
    "following": 300.0,
    "follower_following_ratio": 0.83,
    "posts_per_day": 2.0,
    "comments_per_day": 3.0,
    "average_posting_interval_seconds": 21600.0,  # 6 hours
    "engagement_rate": 0.03,  # 3%
    "duplicate_content_ratio": 0.05,
    "hashtag_repetition_rate": 0.10,
}


def extract_user_features(profile: UserProfile | None) -> dict[str, float]:
    """Extract raw and engineered tabular features from UserProfile with missing value imputation.

    Engineered Features:
    - follower_following_ratio: followers / max(1, following)
    - log transforms for highly skewed count metrics
    """
    if profile is None:
        return FEATURE_DEFAULTS.copy()

    # Followers / Following
    followers = float(max(0, profile.followers))
    following = float(max(0, profile.following))
    ff_ratio = followers / max(1.0, following)

    # Account Age
    age = (
        float(profile.account_age_days)
        if profile.account_age_days is not None
        else FEATURE_DEFAULTS["account_age_days"]
    )

    # Activity Velocities
    posts_per_day = (
        float(profile.posts_per_day)
        if (profile.posts_per_day is not None and profile.posts_per_day > 0)
        else FEATURE_DEFAULTS["posts_per_day"]
    )
    comments_per_day = (
        float(profile.comments_per_day)
        if (profile.comments_per_day is not None and profile.comments_per_day > 0)
        else FEATURE_DEFAULTS["comments_per_day"]
    )

    # Posting Interval
    avg_interval = (
        float(profile.average_posting_interval_seconds)
        if profile.average_posting_interval_seconds is not None
        else (86400.0 / max(0.1, posts_per_day))
    )

    # Engagement & Content Ratios
    engagement = (
        float(profile.engagement_rate)
        if profile.engagement_rate is not None
        else FEATURE_DEFAULTS["engagement_rate"]
    )
    duplicate_ratio = (
        float(profile.duplicate_content_ratio)
        if profile.duplicate_content_ratio is not None
        else FEATURE_DEFAULTS["duplicate_content_ratio"]
    )
    hashtag_rep = (
        float(profile.hashtag_repetition_rate)
        if profile.hashtag_repetition_rate is not None
        else FEATURE_DEFAULTS["hashtag_repetition_rate"]
    )

    return {
        "account_age_days": max(0.0, age),
        "followers": followers,
        "following": following,
        "follower_following_ratio": round(ff_ratio, 4),
        "posts_per_day": round(max(0.0, posts_per_day), 4),
        "comments_per_day": round(max(0.0, comments_per_day), 4),
        "average_posting_interval_seconds": round(max(0.0, avg_interval), 2),
        "engagement_rate": round(max(0.0, min(1.0, engagement)), 4),
        "duplicate_content_ratio": round(max(0.0, min(1.0, duplicate_ratio)), 4),
        "hashtag_repetition_rate": round(max(0.0, min(1.0, hashtag_rep)), 4),
    }


def vectorize_features(features_dict: dict[str, float]) -> np.ndarray:
    """Convert extracted features dictionary into an ordered 1D numpy array with log-scaling."""
    vector = []
    for name in FEATURE_NAMES:
        val = features_dict.get(name, FEATURE_DEFAULTS[name])
        # Apply log1p to heavily skewed power-law metrics
        if name in ("followers", "following", "account_age_days", "average_posting_interval_seconds"):
            vector.append(math.log1p(max(0.0, val)))
        else:
            vector.append(val)
    return np.array(vector, dtype=float)
