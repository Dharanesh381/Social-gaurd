"""Module 5: Score Fusion and Explainable Decision Engine."""

from typing import Any

from app.schemas.domain_models import CredibilityClassification

# Initial default weights as defined in specifications
DEFAULT_WEIGHTS: dict[str, float] = {
    "comment_score": 0.20,
    "evidence_score": 0.40,
    "behaviour_score": 0.15,
    "similarity_score": 0.25,
}


def classify_credibility_score(score: float) -> CredibilityClassification:
    """Map continuous score [0.0, 100.0] into standardized 5-tier classification categories.

    Thresholds:
    - 80.0 – 100.0: LIKELY REAL
    - 60.0 – 79.99: PROBABLY REAL
    - 40.0 – 59.99: UNCERTAIN
    - 20.0 – 39.99: PROBABLY FAKE
    - 0.0  – 19.99: LIKELY FAKE
    """
    bounded = max(0.0, min(100.0, score))
    if bounded >= 80.0:
        return CredibilityClassification.LIKELY_REAL
    elif bounded >= 60.0:
        return CredibilityClassification.PROBABLY_REAL
    elif bounded >= 40.0:
        return CredibilityClassification.UNCERTAIN
    elif bounded >= 20.0:
        return CredibilityClassification.PROBABLY_FAKE
    else:
        return CredibilityClassification.LIKELY_FAKE


class ScoreFusionEngine:
    """Module 5: Fuses normalized scores from Modules 1-4 into a consolidated credibility score,

    computes modular contribution points, confidence bounds, and generates a structured verdict.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self._validate_weights(self.weights)

    @staticmethod
    def _validate_weights(weights: dict[str, float]) -> None:
        """Ensure all required module keys exist and sum approximately to 1.0."""
        required_keys = {"comment_score", "evidence_score", "behaviour_score", "similarity_score"}
        for k in required_keys:
            if k not in weights:
                raise ValueError(f"Missing weight key '{k}' in fusion configuration.")
            if weights[k] < 0.0 or weights[k] > 1.0:
                raise ValueError(f"Weight '{k}' must be between 0.0 and 1.0. Received {weights[k]}.")

        total = sum(weights.values())
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Module weights must sum to 1.0. Current sum: {total:.4f}")

    @staticmethod
    def normalize_and_validate_score(
        score: float | None, module_name: str, fallback_score: float = 50.0
    ) -> tuple[float, list[str]]:
        """Validate and clamp an individual module score to [0.0, 100.0].

        Returns:
            Tuple[validated_score: float, flags: List[str]]
        """
        flags: list[str] = []
        if score is None:
            flags.append(f"{module_name.upper()}_SCORE_MISSING_FALLBACK_APPLIED")
            return fallback_score, flags

        try:
            val = float(score)
        except (ValueError, TypeError):
            flags.append(f"{module_name.upper()}_SCORE_INVALID_FALLBACK_APPLIED")
            return fallback_score, flags

        if val < 0.0:
            flags.append(f"{module_name.upper()}_SCORE_OUT_OF_BOUNDS_CLAMPED_TO_0")
            val = 0.0
        elif val > 100.0:
            flags.append(f"{module_name.upper()}_SCORE_OUT_OF_BOUNDS_CLAMPED_TO_100")
            val = 100.0

        return val, flags

    def fuse_scores(
        self,
        comment_score: float | None,
        evidence_score: float | None,
        behaviour_score: float | None,
        similarity_score: float | None,
        custom_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Execute linear weighted score fusion, contribution breakdown, and confidence evaluation.

        Formula:
        Final Score = 0.20 * Comment + 0.40 * Evidence + 0.15 * Behaviour + 0.25 * Similarity

        Returns:
            Dict containing:
            - final_score: float [0.0 - 100.0]
            - classification: CredibilityClassification enum value string
            - formula_applied: str
            - weights_applied: Dict[str, float]
            - module_contributions: Dict[str, float] (Points contributed out of 100)
            - normalized_input_scores: Dict[str, float]
            - confidence_interval: [lower_bound, upper_bound]
            - confidence_level: "HIGH" | "MEDIUM" | "LOW"
            - flags: List[str]
            - summary_explanation: str
        """
        active_weights = custom_weights or self.weights
        self._validate_weights(active_weights)

        all_flags: list[str] = []

        # Step 1: Validate and Normalize each score
        norm_comment, f_comm = self.normalize_and_validate_score(comment_score, "comment")
        norm_evidence, f_evid = self.normalize_and_validate_score(evidence_score, "evidence")
        norm_behaviour, f_behav = self.normalize_and_validate_score(behaviour_score, "behaviour")
        norm_similarity, f_simil = self.normalize_and_validate_score(similarity_score, "similarity")

        all_flags.extend(f_comm + f_evid + f_behav + f_simil)

        # Step 2: Compute Modular Contributions
        contrib_comment = round(active_weights["comment_score"] * norm_comment, 3)
        contrib_evidence = round(active_weights["evidence_score"] * norm_evidence, 3)
        contrib_behaviour = round(active_weights["behaviour_score"] * norm_behaviour, 3)
        contrib_similarity = round(active_weights["similarity_score"] * norm_similarity, 3)

        # Step 3: Compute Fused Final Score
        final_score = round(
            contrib_comment + contrib_evidence + contrib_behaviour + contrib_similarity,
            2,
        )

        # Clamp just in case of float precision edge cases
        final_score = max(0.0, min(100.0, final_score))

        # Step 4: Classification
        classification = classify_credibility_score(final_score)

        # Step 5: Confidence Calculation
        # Confidence is high when primary signals (Evidence + Similarity) are available
        # and not fallback default values
        missing_count = sum(
            1 for s in [comment_score, evidence_score, behaviour_score, similarity_score] if s is None
        )

        # Variance across module scores
        scores_list = [norm_comment, norm_evidence, norm_behaviour, norm_similarity]
        variance = sum((s - (sum(scores_list) / 4.0)) ** 2 for s in scores_list) / 4.0
        std_dev = variance ** 0.5

        if missing_count == 0 and std_dev < 15.0:
            confidence_level = "HIGH"
            margin = 3.5
        elif missing_count <= 1:
            confidence_level = "MEDIUM"
            margin = 6.0
        else:
            confidence_level = "LOW"
            margin = 10.0
            all_flags.append("MULTIPLE_MODULE_SCORES_MISSING_LOW_CONFIDENCE")

        confidence_interval = [
            round(max(0.0, final_score - margin), 2),
            round(min(100.0, final_score + margin), 2),
        ]

        # Step 6: Formulate plain-language diagnostic explanation
        summary_explanation = (
            f"Final Credibility Score is {final_score:.1f}/100 ({classification.value}). "
            f"Evidence Verification contributed {contrib_evidence:.1f} pts (weight {active_weights['evidence_score']*100:.0f}%), "
            f"Similar Content contributed {contrib_similarity:.1f} pts (weight {active_weights['similarity_score']*100:.0f}%), "
            f"Comment Analysis contributed {contrib_comment:.1f} pts (weight {active_weights['comment_score']*100:.0f}%), "
            f"and User Behaviour contributed {contrib_behaviour:.1f} pts (weight {active_weights['behaviour_score']*100:.0f}%)."
        )

        return {
            "final_score": final_score,
            "classification": classification.value,
            "formula_applied": "0.20*Comment + 0.40*Evidence + 0.15*Behaviour + 0.25*Similarity",
            "weights_applied": active_weights,
            "normalized_input_scores": {
                "comment_score": norm_comment,
                "evidence_score": norm_evidence,
                "behaviour_score": norm_behaviour,
                "similarity_score": norm_similarity,
            },
            "module_contributions": {
                "comment_score": contrib_comment,
                "evidence_score": contrib_evidence,
                "behaviour_score": contrib_behaviour,
                "similarity_score": contrib_similarity,
            },
            "confidence_level": confidence_level,
            "confidence_interval": confidence_interval,
            "flags": all_flags,
            "summary_explanation": summary_explanation,
        }


score_fusion_engine = ScoreFusionEngine()
