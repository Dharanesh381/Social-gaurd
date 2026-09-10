"""Unit tests for Explainability Engine across real-like, fake-like, and uncertain cases."""

import pytest

from app.modules.score_fusion.explainability import ExplainabilityEngine


@pytest.fixture
def xai_engine():
    return ExplainabilityEngine()


def test_real_like_case_explanation(xai_engine: ExplainabilityEngine):
    """Test explainability output on a highly credible post supported by fact-checkers and organic discussion."""
    module_breakdowns = {
        "evidence": {
            "score": 98.0,
            "status": "SUPPORTED",
            "fact_checks": [
                {"publisher": "Reuters Fact Check", "normalized_truth_score": 1.0}
            ],
            "flags": ["VERIFIED_BY_FACT_CHECKERS"],
        },
        "similarity": {
            "score": 85.0,
            "recycled_content": False,
            "text_similarity": 0.20,
            "flags": [],
        },
        "comments": {
            "score": 88.0,
            "metrics": {"duplicate_ratio": 0.02, "comment_count": 15},
            "flags": [],
        },
        "user_behaviour": {
            "score": 82.0,
            "anomaly_score": 0.15,
            "flags": [],
        },
    }

    result = xai_engine.generate_explanation(
        final_score=89.5,
        classification="LIKELY REAL",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.10,
    )

    assert "LIKELY REAL" in result["summary"]
    assert len(result["positive_factors"]) >= 3
    assert len(result["negative_factors"]) == 0

    # Strongest positive signal is Evidence Verification (impact_weight 0.40)
    top_pos = result["positive_factors"][0]
    assert top_pos["module"] == "evidence_verification"
    assert "Reuters Fact Check" in top_pos["factor"]

    # Check decoupled AI probability
    assert any("human-written stylistic distribution" in note for note in result["confidence_notes"])


def test_fake_like_case_explanation(xai_engine: ExplainabilityEngine):
    """Test explainability output on a debunked hoax with bot copypasta and recycled media."""
    module_breakdowns = {
        "evidence": {
            "score": 0.0,
            "status": "CONTRADICTED",
            "fact_checks": [
                {"publisher": "Snopes", "normalized_truth_score": 0.0}
            ],
            "flags": ["DEBUNKED_BY_FACT_CHECKERS"],
        },
        "similarity": {
            "score": 25.0,
            "recycled_content": True,
            "earliest_matching_timestamp": "2020-03-15T08:30:00+00:00",
            "flags": ["MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE"],
        },
        "comments": {
            "score": 35.0,
            "metrics": {"duplicate_ratio": 0.75, "comment_count": 20},
            "flags": ["HIGH_DUPLICATE_COMMENT_RATIO", "TEMPORAL_BURST_ACTIVITY_DETECTED"],
        },
        "user_behaviour": {
            "score": 28.0,
            "anomaly_score": 0.85,
            "flags": ["ANOMALOUS_BEHAVIOURAL_PATTERN", "NEW_ACCOUNT_HIGH_POSTING_VELOCITY"],
        },
    }

    result = xai_engine.generate_explanation(
        final_score=16.5,
        classification="LIKELY FAKE",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.85,
    )

    assert "LIKELY FAKE" in result["summary"]
    assert len(result["negative_factors"]) >= 3

    # Ranked negative factors
    top_neg = result["negative_factors"][0]
    assert top_neg["module"] == "evidence_verification"
    assert "Evidence strongly contradicts the claim" in top_neg["factor"]

    # Verify presence of specific multi-module explanations
    assert "Similar content was found from an earlier timestamp" in result["module_explanations"]["similar_content"]
    assert "Multiple repeated/near-duplicate comments were detected" in result["module_explanations"]["comment_analysis"]
    assert "anomalous behavioural patterns" in result["module_explanations"]["user_behaviour"]

    # Verify decoupled AI generation note
    assert any("high probability (85.0%) of synthetic/AI generation" in note for note in result["confidence_notes"])


def test_uncertain_case_neutral_explanation(xai_engine: ExplainabilityEngine):
    """Test explainability output when no fact-check is found and claim veracity remains unverified."""
    module_breakdowns = {
        "evidence": {
            "score": 50.0,
            "status": "NO_FACT_CHECK_FOUND",
            "fact_checks": [],
            "flags": ["NO_FACT_CHECKS_FOUND"],
        },
        "similarity": {
            "score": 75.0,
            "recycled_content": False,
            "text_similarity": 0.10,
            "flags": [],
        },
        "comments": {
            "score": 60.0,
            "metrics": {"duplicate_ratio": 0.05, "comment_count": 3},
            "flags": [],
        },
        "user_behaviour": {
            "score": 65.0,
            "anomaly_score": 0.20,
            "flags": [],
        },
    }

    result = xai_engine.generate_explanation(
        final_score=60.25,
        classification="PROBABLY REAL",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.45,
    )

    assert "No existing fact-check was found" in result["module_explanations"]["evidence_verification"]
    assert any("Absence of indexed fact-checks does not verify or disprove" in note for note in result["confidence_notes"])
