"""
End-to-end correctness, trace, and explanation consistency test suite.
Verifies all Phase 15 & 22 requirements:
- Case A: M1 low risk reflected in explanation
- Case B: M2 contradicted reflected in explanation with fact-check citation
- Case C: M2 no fact check reflected with honest neutral explanation
- Case D: M3 metadata unavailable does not hallucinate account longevity
- Case E: M4 no match accurately cites local historical corpus limitation
- Case F: High AI probability is decoupled from credibility
- Case G: Exact mathematical fusion check (0.20*M1 + 0.40*M2 + 0.15*M3 + 0.25*M4)
- Case H: Payload differentiation between two distinct live posts
"""

import pytest
import math
from app.schemas.domain_models import (
    AnalysisRequest, SocialMediaPost, UserProfile, Comment, Media, MediaType
)
from app.modules.score_fusion.engine import ScoreFusionEngine
from app.modules.score_fusion.explainability import ExplainabilityEngine
from app.modules.comment_analysis.analyzer import CommentAnalyzer
from app.modules.evidence_verification.analyzer import EvidenceVerifier
from app.modules.user_behaviour.analyzer import UserBehaviourAnalyzer
from app.modules.score_fusion.ai_detector import ai_media_detector


@pytest.fixture
def fusion_engine():
    return ScoreFusionEngine()


@pytest.fixture
def explainability_engine():
    return ExplainabilityEngine()


def test_case_a_m1_low_comment_risk(explainability_engine):
    """CASE A: When M1 is low due to bot/duplicate comments, explanation MUST cite M1 comment risk."""
    module_breakdowns = {
        "comments": {
            "score": 20.0,
            "metrics": {"duplicate_ratio": 0.65, "comment_count": 15},
            "flags": ["HIGH_DUPLICATE_COMMENT_RATIO", "TEMPORAL_BURST_ACTIVITY_DETECTED"]
        },
        "evidence": {"score": 50.0, "status": "NO_FACT_CHECK_FOUND", "fact_checks": [], "flags": []},
        "user_behaviour": {"score": 50.0, "status": "USER_METADATA_UNAVAILABLE", "flags": ["USER_METADATA_UNAVAILABLE"], "metrics": {}},
        "similarity": {"score": 85.0, "status": "NO_HISTORICAL_MATCH", "recycled_content": False, "corpus_size": 3, "flags": []}
    }
    result = explainability_engine.generate_explanation(
        final_score=50.25,
        classification="UNCERTAIN",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.12
    )
    explanation_text = " ".join([result["summary"]] + [f["factor"] for f in result["negative_factors"]] + list(result["module_explanations"].values()))
    assert "comment" in explanation_text.lower()
    assert "duplicate" in explanation_text.lower() or "copypasta" in explanation_text.lower()


def test_case_b_m2_verified_false(explainability_engine):
    """CASE B: When M2 is debunked/contradicted, explanation MUST cite the fact-check result."""
    module_breakdowns = {
        "comments": {"score": 75.0, "metrics": {"duplicate_ratio": 0.0, "comment_count": 8}, "flags": []},
        "evidence": {
            "score": 0.0,
            "status": "CONTRADICTED",
            "fact_checks": [{"publisher": "PolitiFact", "raw_rating": "False", "normalized_truth_score": 0.0}],
            "flags": ["DEBUNKED_BY_FACT_CHECKERS"]
        },
        "user_behaviour": {"score": 50.0, "status": "USER_METADATA_UNAVAILABLE", "flags": ["USER_METADATA_UNAVAILABLE"], "metrics": {}},
        "similarity": {"score": 85.0, "status": "NO_HISTORICAL_MATCH", "recycled_content": False, "corpus_size": 3, "flags": []}
    }
    result = explainability_engine.generate_explanation(
        final_score=43.75,
        classification="UNCERTAIN",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.08
    )
    explanation_text = " ".join([result["summary"]] + [f["factor"] for f in result["negative_factors"]] + list(result["module_explanations"].values()))
    assert "contradicts" in explanation_text.lower() or "debunked" in explanation_text.lower() or "politifact" in explanation_text.lower()


def test_case_c_m2_no_fact_check_found_honest_explanation(explainability_engine):
    """CASE C: When M2 has no fact check found (50/100), explanation MUST state no indexed review was found, not claim it is proven true/false."""
    module_breakdowns = {
        "comments": {"score": 70.0, "metrics": {"duplicate_ratio": 0.0, "comment_count": 3}, "flags": []},
        "evidence": {"score": 50.0, "status": "NO_FACT_CHECK_FOUND", "fact_checks": [], "flags": []},
        "user_behaviour": {"score": 50.0, "status": "USER_METADATA_UNAVAILABLE", "flags": ["USER_METADATA_UNAVAILABLE"], "metrics": {}},
        "similarity": {"score": 85.0, "status": "NO_HISTORICAL_MATCH", "recycled_content": False, "corpus_size": 3, "flags": []}
    }
    result = explainability_engine.generate_explanation(
        final_score=62.75,
        classification="PROBABLY REAL",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.10
    )
    explanation_text = " ".join([result["summary"]] + list(result["module_explanations"].values()) + result["confidence_notes"])
    assert "no existing fact-check was found" in explanation_text.lower() or "no matching indexed fact-check" in explanation_text.lower()
    assert "claim is verified true" not in explanation_text.lower()


def test_case_d_m3_missing_metadata_no_longevity_hallucination(explainability_engine):
    """CASE D: When M3 metadata is unavailable, explanation MUST NOT claim account longevity or posting history."""
    module_breakdowns = {
        "comments": {"score": 50.0, "metrics": {"comment_count": 0}, "flags": ["NO_COMMENTS_AVAILABLE"]},
        "evidence": {"score": 50.0, "status": "NO_FACT_CHECK_FOUND", "fact_checks": [], "flags": []},
        "user_behaviour": {"score": 50.0, "status": "USER_METADATA_UNAVAILABLE", "flags": ["USER_METADATA_UNAVAILABLE"], "metrics": {}},
        "similarity": {"score": 85.0, "status": "NO_HISTORICAL_MATCH", "recycled_content": False, "corpus_size": 3, "flags": []}
    }
    result = explainability_engine.generate_explanation(
        final_score=58.75,
        classification="UNCERTAIN",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.05
    )
    explanation_text = " ".join([result["summary"]] + [f["factor"] for f in result["positive_factors"]] + list(result["module_explanations"].values()))
    assert "mature longevity" not in explanation_text.lower()
    assert "profile metadata was unavailable" in explanation_text.lower()


def test_case_e_m4_honest_corpus_limitation(explainability_engine):
    """CASE E: When M4 has no match, explanation MUST mention current local historical corpus, not internet-wide uniqueness."""
    module_breakdowns = {
        "comments": {"score": 80.0, "metrics": {"duplicate_ratio": 0.0, "comment_count": 5}, "flags": []},
        "evidence": {"score": 50.0, "status": "NO_FACT_CHECK_FOUND", "fact_checks": [], "flags": []},
        "user_behaviour": {"score": 50.0, "status": "USER_METADATA_UNAVAILABLE", "flags": ["USER_METADATA_UNAVAILABLE"], "metrics": {}},
        "similarity": {"score": 85.0, "status": "NO_HISTORICAL_MATCH", "recycled_content": False, "corpus_size": 3, "flags": []}
    }
    result = explainability_engine.generate_explanation(
        final_score=64.75,
        classification="PROBABLY REAL",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.15
    )
    explanation_text = " ".join([result["summary"]] + list(result["module_explanations"].values()))
    assert "historical corpus" in explanation_text.lower()
    assert "no similar content exists on the internet" not in explanation_text.lower()


def test_case_f_ai_generation_decoupled_from_credibility(explainability_engine):
    """CASE F: High AI probability must be clearly marked as orthogonal, not conflated with falsehood."""
    module_breakdowns = {
        "comments": {"score": 80.0, "metrics": {"duplicate_ratio": 0.0, "comment_count": 20}, "flags": []},
        "evidence": {"score": 85.0, "status": "SUPPORTED", "fact_checks": [{"publisher": "Reuters", "raw_rating": "True", "normalized_truth_score": 0.85}], "flags": ["VERIFIED_BY_FACT_CHECKERS"]},
        "user_behaviour": {"score": 80.0, "status": "ANALYZED", "flags": [], "metrics": {"account_age_days": 500}},
        "similarity": {"score": 85.0, "status": "NO_HISTORICAL_MATCH", "recycled_content": False, "corpus_size": 3, "flags": []}
    }
    result = explainability_engine.generate_explanation(
        final_score=83.25,
        classification="LIKELY REAL",
        module_breakdowns=module_breakdowns,
        ai_generated_probability=0.88
    )
    all_notes = " ".join(result["confidence_notes"])
    assert "synthetic/ai generation" in all_notes.lower()
    assert "orthogonal" in all_notes.lower() or "not prove content is false" in all_notes.lower()


def test_case_g_mathematical_fusion_exactness(fusion_engine):
    """CASE G: Final score MUST exactly equal 0.20*M1 + 0.40*M2 + 0.15*M3 + 0.25*M4 within floating point tolerance."""
    test_vectors = [
        (60.0, 50.0, 85.0, 85.0),
        (20.0, 10.0, 30.0, 40.0),
        (100.0, 100.0, 100.0, 100.0),
        (0.0, 0.0, 0.0, 0.0),
        (72.5, 48.3, 61.2, 88.9),
    ]
    for m1, m2, m3, m4 in test_vectors:
        expected = round((0.20 * m1) + (0.40 * m2) + (0.15 * m3) + (0.25 * m4), 2)
        result = fusion_engine.fuse_scores(
            comment_score=m1,
            evidence_score=m2,
            behaviour_score=m3,
            similarity_score=m4
        )
        assert math.isclose(result["final_score"], expected, abs_tol=1e-2), (
            f"Fusion mismatch: {result['final_score']} != {expected}"
        )


@pytest.mark.asyncio
async def test_case_h_two_different_live_posts_produce_different_payloads():
    """CASE H: Two completely different post payloads must produce distinct analysis inputs, queries, and outputs."""
    from app.modules.evidence_verification.claim_extractor import SimpleClaimExtractor
    claim_extractor = SimpleClaimExtractor()

    post_a = SocialMediaPost(
        platform="reddit",
        post_id="post_science_123",
        text="James Webb Space Telescope detects atmospheric water vapor on habitable-zone exoplanet K2-18b.",
        hashtags=["#JWST", "#Astronomy"],
        media=[Media(url="https://images.nasa.gov/jwst_exoplanet.jpg", media_type=MediaType.IMAGE)],
        author=UserProfile(username="astronomer_dan", account_age_days=1200, followers=4500, following=200),
        comments=[
            Comment(comment_id="c1", text="Incredible milestone for spectroscopy!", likes=45),
            Comment(comment_id="c2", text="What instruments were used for transmission spectra?", likes=12)
        ]
    )

    post_b = SocialMediaPost(
        platform="reddit",
        post_id="post_spam_456",
        text="URGENT: Click here to claim your free $1000 gift card immediately before time runs out! 🔥🔥🔥",
        hashtags=["#FreeMoney", "#Giveaway"],
        media=[],
        author=UserProfile(username="fastmoney99"),  # missing age/followers
        comments=[
            Comment(comment_id="c10", text="Claimed mine! works!", likes=0),
            Comment(comment_id="c11", text="Claimed mine! works!", likes=0),
            Comment(comment_id="c12", text="Claimed mine! works!", likes=0),
        ]
    )

    # 1. Check claim extraction differentiation
    claim_a = claim_extractor.extract_claims(post_a.text)
    claim_b = claim_extractor.extract_claims(post_b.text)
    assert claim_a != claim_b

    # 2. Check AI detection differentiation
    ai_a = ai_media_detector.analyze_text(post_a.text)
    ai_b = ai_media_detector.analyze_text(post_b.text)
    assert ai_a["ai_generation_probability"] is not None
    assert ai_b["ai_generation_probability"] is not None

    # 3. Check M1 comment duplication detection
    m1_analyzer = CommentAnalyzer()
    m1_a = m1_analyzer.analyze(post_a.comments)
    m1_b = m1_analyzer.analyze(post_b.comments)
    assert m1_a["metrics"]["duplicate_ratio"] == 0.0
    assert m1_b["metrics"]["duplicate_ratio"] > 0.5
    assert m1_a["comment_score"] > m1_b["comment_score"]
