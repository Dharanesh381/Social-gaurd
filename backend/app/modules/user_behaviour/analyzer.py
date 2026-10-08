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
                "status": str,
                "metrics": Dict[str, Any],
                "flags": List[str],
                "explanation": str
            }
        """
        flags: list[str] = []

        # ----------------------------------------------------------------------
        # Edge Case 1: Missing profile or unavailable metadata
        # If account age is None and followers/following are 0 (e.g. basic extracted handle),
        # treat as unavailable metadata and return neutral baseline 50.0
        # ----------------------------------------------------------------------
        is_metadata_unavailable = (
            profile is None
            or (profile.account_age_days is None and profile.followers == 0 and profile.following == 0)
        )

        if is_metadata_unavailable:
            username = profile.username if profile else "unknown"
            return {
                "score": 50.0,
                "behaviour_score": 50.0,  # Neutral baseline
                "anomaly_score": 0.0,
                "is_anomalous": False,
                "status": "USER_METADATA_UNAVAILABLE",
                "metrics": {
                    "account_age_days": None,
                    "followers": None,
                    "following": None,
                    "follower_following_ratio": None,
                    "posts_per_day": None,
                    "comments_per_day": None,
                    "average_posting_interval_seconds": None,
                    "engagement_rate": None,
                    "duplicate_content_ratio": None,
                    "hashtag_repetition_rate": None,
                    "is_anomalous": False,
                },
                "flags": ["USER_METADATA_UNAVAILABLE"],
                "explanation": (
                    f"User profile metadata for '{username}' was not available from the page. "
                    "Assigned neutral baseline score (50/100). Behavioral anomaly does not prove content is fake."
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
        anomaly_reasons: list[str] = []

        # Flag 1: Brand new account with aggressive posting
        if features["account_age_days"] < 7 and features["posts_per_day"] > 20:
            flags.append("NEW_ACCOUNT_HIGH_POSTING_VELOCITY")
            anomaly_reasons.append(f"fresh account ({features['account_age_days']:.0f} days) with aggressive posting velocity")

        # Flag 2: Extreme follower asymmetry (following >> followers)
        if features["following"] > 1000 and features["follower_following_ratio"] < 0.05:
            flags.append("EXTREME_FOLLOWER_ASYMMETRY")
            anomaly_reasons.append("extreme follower-to-following imbalance")

        # Flag 3: High timeline duplicate content ratio
        if features["duplicate_content_ratio"] >= 0.40:
            flags.append("HIGH_TIMELINE_DUPLICATION_RATIO")
            anomaly_reasons.append(f"high timeline duplicate content ratio ({features['duplicate_content_ratio'] * 100:.0f}%)")

        # Flag 4: Hashtag spamming
        if features["hashtag_repetition_rate"] >= 0.50:
            flags.append("EXCESSIVE_HASHTAG_REPETITION")
            anomaly_reasons.append(f"excessive hashtag repetition ({features['hashtag_repetition_rate'] * 100:.0f}%)")

        # Flag 5: Extreme posting velocity
        if features["posts_per_day"] > 50:
            flags.append("EXTREME_POSTING_VELOCITY")
            anomaly_reasons.append(f"extreme posting velocity ({features['posts_per_day']:.0f} posts/day)")

        # Flag 6: Unnatural posting interval
        if features["average_posting_interval_seconds"] < 60.0 and features["posts_per_day"] > 20:
            flags.append("UNNATURALLY_RAPID_POSTING_INTERVAL")
            anomaly_reasons.append("rapid automated posting interval (< 60s)")

        # Flag 7: Isolation Forest outlier
        if is_anomalous:
            flags.append("ANOMALOUS_BEHAVIOURAL_PATTERN")
            if not anomaly_reasons:
                anomaly_reasons.append("multivariate behavioural anomaly detected by Isolation Forest")

        # ----------------------------------------------------------------------
        # Step 5: Transparent Behaviour Score Calculation (0 - 100)
        #
        # High score (80-100) = Mature, balanced, organic behavioral profile.
        # Moderate score (50-79) = High activity or newer account with organic content.
        # Low score (0-49)   = Suspicious automation, high repetition, fresh bot profile.
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

        # Penalty 4: Extreme posting velocity (> 50 posts/day: up to 15 pts)
        if features["posts_per_day"] > 50:
            vel_penalty = min(15.0, ((features["posts_per_day"] - 50.0) / 50.0) * 15.0)
            base_score -= vel_penalty

        # Penalty 5: Hashtag repetition (> 40%: up to 10 pts)
        if features["hashtag_repetition_rate"] > 0.40:
            base_score -= min(10.0, (features["hashtag_repetition_rate"] - 0.40) * 16.67)

        # Penalty 6: Extreme follower asymmetry
        if features["following"] > 1000 and features["follower_following_ratio"] < 0.05:
            base_score -= 10.0

        behaviour_score = round(max(0.0, min(100.0, base_score)), 2)

        # ----------------------------------------------------------------------
        # Step 6: Constructive, Balanced Explanation with Critical Rule
        # ----------------------------------------------------------------------
        if behaviour_score >= 75.0:
            explanation = (
                f"Account '{profile.username}' exhibits mature, balanced engagement patterns "
                f"with normal posting velocity ({features['posts_per_day']} posts/day) and longevity ({features['account_age_days']:.0f} days)."
            )
        elif behaviour_score >= 50.0:
            explanation = (
                f"Account '{profile.username}' shows moderate behavioral variances ({features['posts_per_day']} posts/day). "
                f"Note: High activity or new accounts do not inherently indicate inauthenticity. Behavioral anomaly does not prove post is fake."
            )
        else:
            reasons_str = "; ".join(anomaly_reasons) if anomaly_reasons else "unusual velocity"
            explanation = (
                f"Account '{profile.username}' displays anomalous behavioural signals ({reasons_str}). "
                f"CRITICAL NOTE: Behavioral anomaly indicates unusual account automation or velocity, but does NOT directly mean that the content is fake."
            )

        combined_metrics = {
            **features,
            **stat_metrics,
            "raw_isolation_forest_score": raw_decision,
            "is_anomalous": is_anomalous,
        }

        return {
            "score": behaviour_score,
            "behaviour_score": behaviour_score,
            "anomaly_score": norm_anomaly_score,
            "is_anomalous": is_anomalous,
            "status": "COMPLETED",
            "metrics": combined_metrics,
            "flags": flags,
            "explanation": explanation,
        }


user_behaviour_analyzer = UserBehaviourAnalyzer()
