"""Isolation Forest model trainer and statistical anomaly detector."""

import logging

import numpy as np
from sklearn.ensemble import IsolationForest

from app.modules.user_behaviour.feature_extractor import (
    FEATURE_DEFAULTS,
    vectorize_features,
)

logger = logging.getLogger(__name__)

# Baseline distribution parameters derived from authentic social media accounts
# Used for statistical Z-score and IQR computations
POPULATION_STATS: dict[str, dict[str, float]] = {
    "posts_per_day": {"mean": 2.5, "std": 3.0, "q25": 0.5, "q75": 3.5},
    "comments_per_day": {"mean": 4.0, "std": 5.0, "q25": 1.0, "q75": 6.0},
    "follower_following_ratio": {"mean": 1.2, "std": 2.0, "q25": 0.5, "q75": 1.5},
    "duplicate_content_ratio": {"mean": 0.05, "std": 0.08, "q25": 0.0, "q75": 0.08},
    "hashtag_repetition_rate": {"mean": 0.12, "std": 0.15, "q25": 0.0, "q75": 0.18},
}


def create_baseline_training_dataset(n_samples: int = 500, random_seed: int = 42) -> np.ndarray:
    """Generate a realistic synthetic training distribution of authentic and varied social media accounts.

    This ensures the model is trained on a distinct baseline distribution,
    completely separate from test and inference inputs.
    """
    rng = np.random.default_rng(random_seed)
    data = []

    for _ in range(n_samples):
        # 90% normal users, 10% high-activity / creator accounts
        is_creator = rng.random() < 0.10

        if is_creator:
            sample = {
                "account_age_days": float(rng.uniform(300, 3000)),
                "followers": float(rng.uniform(5000, 100000)),
                "following": float(rng.uniform(200, 1500)),
                "posts_per_day": float(rng.uniform(3, 12)),
                "comments_per_day": float(rng.uniform(5, 30)),
                "average_posting_interval_seconds": float(rng.uniform(3600, 28800)),
                "engagement_rate": float(rng.uniform(0.02, 0.08)),
                "duplicate_content_ratio": float(rng.uniform(0.0, 0.10)),
                "hashtag_repetition_rate": float(rng.uniform(0.05, 0.30)),
            }
        else:
            sample = {
                "account_age_days": float(rng.uniform(30, 2000)),
                "followers": float(rng.uniform(20, 1500)),
                "following": float(rng.uniform(30, 1000)),
                "posts_per_day": float(rng.exponential(1.8)),
                "comments_per_day": float(rng.exponential(3.0)),
                "average_posting_interval_seconds": float(rng.uniform(14400, 86400)),
                "engagement_rate": float(rng.uniform(0.005, 0.06)),
                "duplicate_content_ratio": float(rng.uniform(0.0, 0.08)),
                "hashtag_repetition_rate": float(rng.uniform(0.0, 0.20)),
            }

        sample["follower_following_ratio"] = sample["followers"] / max(1.0, sample["following"])
        data.append(vectorize_features(sample))

    return np.array(data)


class UserAnomalyDetector:
    """Configurable Isolation Forest and statistical anomaly evaluator."""

    def __init__(
        self,
        contamination: float = 0.08,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

        # Train Isolation Forest on baseline population distribution
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        baseline_X = create_baseline_training_dataset(n_samples=600, random_seed=self.random_state)
        self.model.fit(baseline_X)
        logger.info("Trained Isolation Forest anomaly detector on %d baseline samples.", len(baseline_X))

    def compute_statistical_anomalies(self, features: dict[str, float]) -> dict[str, float]:
        """Compute Z-scores and IQR outlier flags against baseline population parameters."""
        stats_out = {}
        for feature, pop in POPULATION_STATS.items():
            val = features.get(feature, FEATURE_DEFAULTS[feature])
            # Z-score
            z = (val - pop["mean"]) / max(1e-5, pop["std"])
            stats_out[f"{feature}_zscore"] = round(z, 2)

            # IQR
            iqr = pop["q75"] - pop["q25"]
            upper_bound = pop["q75"] + (1.5 * iqr)
            stats_out[f"{feature}_iqr_outlier"] = 1.0 if val > upper_bound else 0.0

        return stats_out

    def predict_anomaly(self, features_dict: dict[str, float]) -> tuple[bool, float, float]:
        """Run Isolation Forest inference.

        Returns:
            Tuple[is_anomalous: bool, raw_decision_function: float, normalized_anomaly_score: float]
            - raw_decision_function: negative indicates anomaly, positive indicates normal
            - normalized_anomaly_score: scaled [0.0, 1.0] where 1.0 = highly anomalous, 0.0 = completely normal
        """
        vec = vectorize_features(features_dict).reshape(1, -1)
        raw_score = float(self.model.decision_function(vec)[0])
        pred = int(self.model.predict(vec)[0])  # -1 for anomaly, 1 for normal

        is_anomalous = pred == -1

        # Normalize raw decision function (typically ranges from -0.3 to +0.25)
        # to [0.0, 1.0] anomaly score
        # Lower decision function = more anomalous
        norm_score = max(0.0, min(1.0, 0.5 - (raw_score * 2.0)))

        return is_anomalous, round(raw_score, 4), round(norm_score, 4)


anomaly_detector = UserAnomalyDetector()
