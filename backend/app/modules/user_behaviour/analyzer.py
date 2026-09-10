"""Module 3: User Behaviour Analysis Engine implementation."""

from typing import Any

from app.modules.user_behaviour.anomaly_detector import (
    UserAnomalyDetector,
    anomaly_detector,
)
from app.modules.user_behaviour.feature_extractor import (
    extract_user_features,
)
from app.schemas.domain_models import UserProfile


class UserBehaviourAnalyzer:
    """Module 3: Analyzes public user/author behavioural metadata using Isolation Forest,

    statistical distributions, and rule-based guardrails.

    CRITICAL RULE:
    Anomalous behaviour indicates unusual automation, spamming, or extreme velocity;
    it DOES NOT mean the content is fake.
    """

    def __init__(self, detector: UserAnomalyDetector | None = None):
        self.detector = detector or anomaly_detector

    def analyze(self, profile: UserProfile | None) -> dict[str, Any]:
        """Execute User Behaviour Analysis pipeline.

        Returns:
            Dict conforming to:
            {
                "behaviour_score": float (0-100),
                "anomaly_score": float (0.0 to 1.0),
                "metrics": Dict[str, Any],
                "flags": List[str],
                "explanation": str
            }
        """
        flags: list[str] = []

        # ----------------------------------------------------------------------
        # Edge Case 1: Missing profile metadata
        # ----------------------------------------------------------------------
        if profile is None:
            return {
                "behaviour_score": 50.0,  # Neutral baseline
                "anomaly_score": 0.0,
                "metrics": {
                    "account_age_days": None,
                    "followers": None,
                    "following": None,
                    "posts_per_day": None,
                    "duplicate_content_ratio": None,
                    "is_anomalous": False,
                },
                "flags": ["USER_METADATA_UNAVAILABLE"],
                "explanation": (
                    "User profile metadata is not publicly available. "
                    "Assigned neutral baseline score."
                ),
            }

        # ----------------------------------------------------------------------
        # Step 1: Feature Extraction & Engineering
        # ----------------------------------------------------------------------
        features = extract_user_features(profile)

        # ----------------------------------------------------------------------
        # Step 2: Isolation Forest Anomaly Detection
        # ----------------------------------------------------------------------
        is_anomalous, raw_decision, norm_anomaly_score = self.detector.predict_anomaly(features)

        # ----------------------------------------------------------------------
        # Step 3: Statistical Z-Score & IQR Features
        # ----------------------------------------------------------------------
        stat_metrics = self.detector.compute_statistical_anomalies(features)

        # ----------------------------------------------------------------------
        # Step 4: Rule-Based Guardrails & Flagging
        # ----------------------------------------------------------------------
        # Flag 1: Brand new account with aggressive posting
        if features["account_age_days"] < 7 and features["posts_per_day"] > 20:
            flags.append("NEW_ACCOUNT_HIGH_POSTING_VELOCITY")

        # Flag 2: Extreme follower asymmetry (following >> followers)
        if features["following"] > 1000 and features["follower_following_ratio"] < 0.05:
            flags.append("EXTREME_FOLLOWER_ASYMMETRY")

        # Flag 3: High timeline duplicate content ratio
        if features["duplicate_content_ratio"] >= 0.40:
            flags.append("HIGH_TIMELINE_DUPLICATION_RATIO")

        # Flag 4: Hashtag spamming
        if features["hashtag_repetition_rate"] >= 0.50:
            flags.append("EXCESSIVE_HASHTAG_REPETITION")

        # Flag 5: Isolation Forest outlier
        if is_anomalous:
            flags.append("ANOMALOUS_BEHAVIOURAL_PATTERN")

        # ----------------------------------------------------------------------
        # Step 5: Transparent Behaviour Score Calculation (0 - 100)
        #
        # High score (80-100) = Mature, balanced, organic behavioral profile.
        # Low score (0-39)   = Suspicious automation, high repetition, fresh bot profile.
        # ----------------------------------------------------------------------
        base_score = 100.0

        # Penalty 1: Isolation Forest Anomaly Penalty (up to 30 pts)
        base_score -= norm_anomaly_score * 30.0

        # Penalty 2: Content Duplication in Timeline (up to 25 pts)
        base_score -= features["duplicate_content_ratio"] * 25.0

        # Penalty 3: New account penalty (< 30 days old: up to 15 pts)
        if features["account_age_days"] < 30:
            age_factor = (30.0 - features["account_age_days"]) / 30.0
            base_score -= age_factor * 15.0

        # Penalty 4: Extreme posting velocity (> 50 posts/day)
        if features["posts_per_day"] > 50:
            base_score -= 15.0

        # Penalty 5: Hashtag repetition (> 40%)
        if features["hashtag_repetition_rate"] > 0.40:
            base_score -= 10.0

        behaviour_score = round(max(0.0, min(100.0, base_score)), 2)

        # ----------------------------------------------------------------------
        # Step 6: Constructive, Balanced Explanation
        # ----------------------------------------------------------------------
        if behaviour_score >= 75.0:
            explanation = (
                f"Account '{profile.username}' exhibits mature, balanced engagement patterns "
                f"with normal posting velocity ({features['posts_per_day']} posts/day)."
            )
        elif behaviour_score >= 50.0:
            explanation = (
                f"Account '{profile.username}' shows moderate behavioral variances. "
                f"Note: High activity or new accounts do not inherently indicate inauthenticity."
            )
        else:
            explanation = (
                f"Account '{profile.username}' displays anomalous behavioural signals "
                f"(high duplicate content or unusual velocity). Note: Anomaly does not prove post is fake."
            )

        combined_metrics = {
            **features,
            **stat_metrics,
            "raw_isolation_forest_score": raw_decision,
            "is_anomalous": is_anomalous,
        }

        return {
            "behaviour_score": behaviour_score,
            "anomaly_score": norm_anomaly_score,
            "metrics": combined_metrics,
            "flags": flags,
            "explanation": explanation,
        }


user_behaviour_analyzer = UserBehaviourAnalyzer()
