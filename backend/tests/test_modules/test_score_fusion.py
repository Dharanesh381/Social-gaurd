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


# ==============================================================================
# 3. EIGHT REQUIRED USER SPECIFICATION TESTS & GUARDRAILS
# ==============================================================================

def test_case_1_all_high_scores(fusion_engine: ScoreFusionEngine):
    """Test 1: All high scores across all modules.

    M1: 90.0, M2: 95.0, M3: 85.0, M4: 90.0
    Math: 0.20*90 + 0.40*95 + 0.15*85 + 0.25*90 = 18 + 38 + 12.75 + 22.5 = 91.25
    Classification: LIKELY REAL
    """
    res = fusion_engine.fuse_and_explain(
        m1=90.0,
        m2=95.0,
        m3=85.0,
        m4=90.0,
    )

    assert res["final_score"] == 91.25
    assert res["classification"] == "LIKELY REAL"
    assert res["confidence_level"] in ("HIGH", "MEDIUM")
    assert res["module_scores"]["comment_analysis"] == 90.0
    assert res["module_scores"]["evidence_verification"] == 95.0
    assert res["module_scores"]["user_behaviour"] == 85.0
    assert res["module_scores"]["similar_content"] == 90.0
    assert res["weighted_contributions"]["comment_analysis"] == 18.0
    assert res["weighted_contributions"]["evidence_verification"] == 38.0
    assert res["weighted_contributions"]["user_behaviour"] == 12.75
    assert res["weighted_contributions"]["similar_content"] == 22.5
    assert len(res["positive_factors"]) >= 1
    assert len(res["negative_factors"]) == 0
    assert "LIKELY REAL" in res["explanation_summary"]


def test_case_2_all_low_scores(fusion_engine: ScoreFusionEngine):
    """Test 2: All low scores across all modules (debunked, coordinated, anomalous, recycled).

    M1: 15.0, M2: 10.0, M3: 20.0, M4: 15.0
    Math: 0.20*15 + 0.40*10 + 0.15*20 + 0.25*15 = 3 + 4 + 3 + 3.75 = 13.75
    Classification: LIKELY FAKE
    """
    res = fusion_engine.fuse_and_explain(
        m1=15.0,
        m2=10.0,
        m3=20.0,
        m4=15.0,
    )

    assert res["final_score"] == 13.75
    assert res["classification"] == "LIKELY FAKE"
    assert res["weighted_contributions"]["comment_analysis"] == 3.0
    assert res["weighted_contributions"]["evidence_verification"] == 4.0
    assert res["weighted_contributions"]["user_behaviour"] == 3.0
    assert res["weighted_contributions"]["similar_content"] == 3.75
    assert len(res["negative_factors"]) >= 1
    assert "LIKELY FAKE" in res["explanation_summary"]


def test_case_3_mixed_scores(fusion_engine: ScoreFusionEngine):
    """Test 3: Mixed scores matching exact user specification example.

    M1: 80.0, M2: 90.0, M3: 70.0, M4: 60.0
    Math: 0.20*80 + 0.40*90 + 0.15*70 + 0.25*60 = 16 + 36 + 10.5 + 15 = 77.5
    Classification: PROBABLY REAL
    """
    res = fusion_engine.fuse_and_explain(
        m1=80.0,
        m2=90.0,
        m3=70.0,
        m4=60.0,
    )

    assert res["final_score"] == 77.5
    assert res["classification"] == "PROBABLY REAL"
    assert res["weighted_contributions"]["comment_analysis"] == 16.0
    assert res["weighted_contributions"]["evidence_verification"] == 36.0
    assert res["weighted_contributions"]["user_behaviour"] == 10.5
    assert res["weighted_contributions"]["similar_content"] == 15.0
    assert "PROBABLY REAL" in res["explanation_summary"]
    assert "Evidence" in res["explanation_summary"]


def test_case_4_uncertain_scores(fusion_engine: ScoreFusionEngine):
    """Test 4: Uncertain scores across all modules (neutral baseline 50).

    M1: 50.0, M2: 50.0, M3: 50.0, M4: 50.0
    Math: 0.20*50 + 0.40*50 + 0.15*50 + 0.25*50 = 10 + 20 + 7.5 + 12.5 = 50.0
    Classification: UNCERTAIN
    """
    res = fusion_engine.fuse_and_explain(
        m1=50.0,
        m2=50.0,
        m3=50.0,
        m4=50.0,
    )

    assert res["final_score"] == 50.0
    assert res["classification"] == "UNCERTAIN"
    assert res["weighted_contributions"]["evidence_verification"] == 20.0


def test_case_5_missing_evidence_guardrail(fusion_engine: ScoreFusionEngine):
    """Test 5: Guardrail 3 - Missing fact-check results MUST NOT automatically classify content as fake.

    M1: 85.0, M2: None (missing fact-check -> neutral 50.0 fallback), M3: 80.0, M4: 80.0
    Math: 0.20*85 (17) + 0.40*50 (20) + 0.15*80 (12) + 0.25*80 (20) = 69.0
    Classification: PROBABLY REAL (not fake!)
    """
    res = fusion_engine.fuse_and_explain(
        comment_score=85.0,
        evidence_score=None,
        behaviour_score=80.0,
        similarity_score=80.0,
    )

    assert res["final_score"] == 69.0
    assert res["classification"] == "PROBABLY REAL"
    assert res["classification"] != "PROBABLY FAKE"
    assert res["classification"] != "LIKELY FAKE"
    assert any("EVIDENCE_SCORE_MISSING_FALLBACK_APPLIED" in f for f in res["flags"])
    assert any("does not verify or disprove" in note.lower() for note in res["confidence_notes"])


def test_case_6_anomalous_behavior_guardrail(fusion_engine: ScoreFusionEngine):
    """Test 6: Guardrail 2 - Behavioral anomaly MUST NOT automatically classify content as fake.

    M1: 90.0, M2: 95.0, M3: 10.0 (anomalous bot-like activity), M4: 85.0
    Math: 0.20*90 (18) + 0.40*95 (38) + 0.15*10 (1.5) + 0.25*85 (21.25) = 78.75
    Classification: PROBABLY REAL (not fake!)
    """
    res = fusion_engine.fuse_and_explain(
        comment_score=90.0,
        evidence_score=95.0,
        behaviour_score=10.0,
        similarity_score=85.0,
    )

    assert res["final_score"] == 78.75
    assert res["classification"] == "PROBABLY REAL"
    assert res["classification"] != "PROBABLY FAKE"
    assert res["classification"] != "LIKELY FAKE"
    # Guardrail explanation verified
    assert any("does not alone prove content falsity" in note.lower() for note in res["confidence_notes"])


def test_case_7_ai_generated_but_factual_content(fusion_engine: ScoreFusionEngine):
    """Test 7: Guardrail 1 - AI-generation probability MUST NOT modify credibility score.

    High AI generation probability (0.95 / 95%) with factual verified signals:
    M1: 90.0, M2: 95.0, M3: 85.0, M4: 90.0
    Score without AI probability = 91.25
    Score with AI probability = 91.25 (EXACTLY UNCHANGED!)
    Classification: LIKELY REAL
    """
    res_without_ai = fusion_engine.fuse_and_explain(
        m1=90.0, m2=95.0, m3=85.0, m4=90.0
    )
    res_with_ai = fusion_engine.fuse_and_explain(
        m1=90.0, m2=95.0, m3=85.0, m4=90.0,
        ai_generated_probability=0.95,
    )

    assert res_with_ai["final_score"] == res_without_ai["final_score"] == 91.25
    assert res_with_ai["classification"] == "LIKELY REAL"
    # Check decoupled AI note
    assert any("orthogonal to factual credibility" in note.lower() for note in res_with_ai["confidence_notes"])


def test_case_8_human_created_but_false_content(fusion_engine: ScoreFusionEngine):
    """Test 8: Human-created but false content is correctly penalized for falsehood despite human authorship.

    Human authorship: AI probability = 0.05 (5%)
    M1: 20.0 (skeptical debunk comments), M2: 0.0 (debunked false claim), M3: 80.0 (mature human user), M4: 25.0 (recycled hoax)
    Math: 0.20*20 (4) + 0.40*0 (0) + 0.15*80 (12) + 0.25*25 (6.25) = 22.25
    Classification: PROBABLY FAKE
    """
    res = fusion_engine.fuse_and_explain(
        m1=20.0,
        m2=0.0,
        m3=80.0,
        m4=25.0,
        ai_generated_probability=0.05,
    )

    assert res["final_score"] == 22.25
    assert res["classification"] == "PROBABLY FAKE"
    assert any("human-written" in note.lower() for note in res["confidence_notes"])
    assert any("does not guarantee factual accuracy" in note.lower() for note in res["confidence_notes"])
    assert len(res["negative_factors"]) >= 1

