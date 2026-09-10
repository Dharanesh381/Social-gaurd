"""Unit tests for Module 5: Score Fusion and Decision Engine."""

import pytest

from app.modules.score_fusion.engine import (
    DEFAULT_WEIGHTS,
    ScoreFusionEngine,
    classify_credibility_score,
)
from app.schemas.domain_models import CredibilityClassification


# ==============================================================================
# 1. CLASSIFICATION THRESHOLD TESTS
# ==============================================================================

def test_classification_threshold_bands():
    """Test precise 5-tier classification threshold mapping."""
    # LIKELY REAL: 80 - 100
    assert classify_credibility_score(100.0) == CredibilityClassification.LIKELY_REAL
    assert classify_credibility_score(80.0) == CredibilityClassification.LIKELY_REAL
    assert classify_credibility_score(85.5) == CredibilityClassification.LIKELY_REAL

    # PROBABLY REAL: 60 - 79.99
    assert classify_credibility_score(79.9) == CredibilityClassification.PROBABLY_REAL
    assert classify_credibility_score(60.0) == CredibilityClassification.PROBABLY_REAL
    assert classify_credibility_score(65.0) == CredibilityClassification.PROBABLY_REAL

    # UNCERTAIN: 40 - 59.99
    assert classify_credibility_score(59.9) == CredibilityClassification.UNCERTAIN
    assert classify_credibility_score(40.0) == CredibilityClassification.UNCERTAIN
    assert classify_credibility_score(50.0) == CredibilityClassification.UNCERTAIN

    # PROBABLY FAKE: 20 - 39.99
    assert classify_credibility_score(39.9) == CredibilityClassification.PROBABLY_FAKE
    assert classify_credibility_score(20.0) == CredibilityClassification.PROBABLY_FAKE
    assert classify_credibility_score(25.0) == CredibilityClassification.PROBABLY_FAKE

    # LIKELY FAKE: 0 - 19.99
    assert classify_credibility_score(19.9) == CredibilityClassification.LIKELY_FAKE
    assert classify_credibility_score(0.0) == CredibilityClassification.LIKELY_FAKE
    assert classify_credibility_score(5.0) == CredibilityClassification.LIKELY_FAKE


# ==============================================================================
# 2. SCORE FUSION ENGINE TESTS
# ==============================================================================

@pytest.fixture
def fusion_engine():
    return ScoreFusionEngine()


def test_high_credibility_fusion(fusion_engine: ScoreFusionEngine):
    """Test high credibility scenario across all modules:

    Comment: 85, Evidence: 95, Behaviour: 80, Similarity: 90
    Expected: 0.20*85 (17) + 0.40*95 (38) + 0.15*80 (12) + 0.25*90 (22.5) = 89.5
    Classification: LIKELY_REAL
    """
    res = fusion_engine.fuse_scores(
        comment_score=85.0,
        evidence_score=95.0,
        behaviour_score=80.0,
        similarity_score=90.0,
    )

    assert res["final_score"] == 89.5
    assert res["classification"] == "LIKELY REAL"
    assert res["module_contributions"]["comment_score"] == 17.0
    assert res["module_contributions"]["evidence_score"] == 38.0
    assert res["module_contributions"]["behaviour_score"] == 12.0
    assert res["module_contributions"]["similarity_score"] == 22.5
    assert res["confidence_level"] in ("HIGH", "MEDIUM")


def test_low_credibility_fusion(fusion_engine: ScoreFusionEngine):
    """Test low credibility / debunked scenario:

    Comment: 30, Evidence: 0 (debunked), Behaviour: 20, Similarity: 25 (recycled)
    Expected: 0.20*30 (6) + 0.40*0 (0) + 0.15*20 (3) + 0.25*25 (6.25) = 15.25
    Classification: LIKELY_FAKE
    """
    res = fusion_engine.fuse_scores(
        comment_score=30.0,
        evidence_score=0.0,
        behaviour_score=20.0,
        similarity_score=25.0,
    )

    assert res["final_score"] == 15.25
    assert res["classification"] == "LIKELY FAKE"
    assert res["module_contributions"]["evidence_score"] == 0.0
    assert res["module_contributions"]["similarity_score"] == 6.25


def test_uncertain_case_neutral_evidence(fusion_engine: ScoreFusionEngine):
    """Test uncertain scenario with missing / neutral evidence:

    Comment: 50, Evidence: 50 (NO_FACT_CHECK_FOUND), Behaviour: 50, Similarity: 50
    Expected: 0.20*50 (10) + 0.40*50 (20) + 0.15*50 (7.5) + 0.25*50 (12.5) = 50.0
    Classification: UNCERTAIN
    """
    res = fusion_engine.fuse_scores(
        comment_score=50.0,
        evidence_score=50.0,
        behaviour_score=50.0,
        similarity_score=50.0,
    )

    assert res["final_score"] == 50.0
    assert res["classification"] == "UNCERTAIN"


def test_boundary_values_clamping(fusion_engine: ScoreFusionEngine):
    """Test extreme boundary values (0.0, 100.0, and out-of-bounds inputs) are clamped."""
    # Min boundary
    res_min = fusion_engine.fuse_scores(0.0, 0.0, 0.0, 0.0)
    assert res_min["final_score"] == 0.0
    assert res_min["classification"] == "LIKELY FAKE"

    # Max boundary
    res_max = fusion_engine.fuse_scores(100.0, 100.0, 100.0, 100.0)
    assert res_max["final_score"] == 100.0
    assert res_max["classification"] == "LIKELY REAL"

    # Out-of-bounds input (-20 and 150)
    res_clamped = fusion_engine.fuse_scores(-20.0, 150.0, 50.0, 50.0)
    # Clamped: 0.20*0 (0) + 0.40*100 (40) + 0.15*50 (7.5) + 0.25*50 (12.5) = 60.0
    assert res_clamped["final_score"] == 60.0
    assert any("CLAMPED_TO_0" in f for f in res_clamped["flags"])
    assert any("CLAMPED_TO_100" in f for f in res_clamped["flags"])


def test_missing_module_scores_fallback(fusion_engine: ScoreFusionEngine):
    """Test that missing module scores (None) use a 50.0 neutral fallback without crashing."""
    res = fusion_engine.fuse_scores(
        comment_score=None,
        evidence_score=80.0,
        behaviour_score=None,
        similarity_score=70.0,
    )
    # Comment fallback: 50.0 -> contrib 10.0
    # Evidence: 80.0 -> contrib 32.0
    # Behaviour fallback: 50.0 -> contrib 7.5
    # Similarity: 70.0 -> contrib 17.5
    # Total: 10 + 32 + 7.5 + 17.5 = 67.0
    assert res["final_score"] == 67.0
    assert res["classification"] == "PROBABLY REAL"
    assert any("COMMENT_SCORE_MISSING_FALLBACK_APPLIED" in f for f in res["flags"])
    assert any("BEHAVIOUR_SCORE_MISSING_FALLBACK_APPLIED" in f for f in res["flags"])


def test_invalid_weights_raise_value_error():
    """Test that invalid weight configurations (sum != 1.0 or missing keys) raise ValueError."""
    with pytest.raises(ValueError):
        ScoreFusionEngine(weights={"comment_score": 0.5, "evidence_score": 0.1})  # Missing keys & sum != 1.0

    with pytest.raises(ValueError):
        ScoreFusionEngine(weights={
            "comment_score": 0.5,
            "evidence_score": 0.5,
            "behaviour_score": 0.5,
            "similarity_score": 0.5,
        })  # Sum is 2.0
