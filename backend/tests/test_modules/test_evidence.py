"""Unit and integration tests for Module 2: Evidence-Based Verification Engine."""

from unittest.mock import AsyncMock, patch
import pytest

from app.modules.evidence_verification.analyzer import EvidenceVerifier
from app.modules.evidence_verification.claim_extractor import SimpleClaimExtractor
from app.modules.evidence_verification.factcheck_client import GoogleFactCheckClient
from app.modules.evidence_verification.normalization import (
    compute_source_credibility,
    normalize_fact_check_rating,
)


# ==============================================================================
# 1. CLAIM EXTRACTION TESTS
# ==============================================================================

def test_claim_extractor_filters_opinions():
    """Test extractor separates verifiable facts from subjective opinions."""
    extractor = SimpleClaimExtractor()
    text = (
        "I think this movie is overrated. "
        "NASA confirmed liquid water was detected on Mars. "
        "In my opinion scientists are wrong. "
        "Global temperatures rose by 1.2 degrees Celsius since pre-industrial times."
    )
    claims = extractor.extract_claims(text)
    assert len(claims) == 2
    assert "NASA confirmed liquid water was detected on Mars" in claims[0]
    assert "Global temperatures rose" in claims[1]


def test_claim_extractor_empty_text():
    """Test claim extraction on empty or whitespace strings."""
    extractor = SimpleClaimExtractor()
    assert extractor.extract_claims("") == []
    assert extractor.extract_claims("   \n\t  ") == []


# ==============================================================================
# 2. RATING NORMALIZATION & SOURCE CREDIBILITY TESTS
# ==============================================================================

def test_normalize_fact_check_rating_mapping():
    """Test continuous score mapping across heterogeneous verdicts."""
    score, cat = normalize_fact_check_rating("False")
    assert score == 0.0
    assert cat == "FALSE"

    score, cat = normalize_fact_check_rating("Pants on Fire")
    assert score == 0.0
    assert cat == "FALSE"

    score, cat = normalize_fact_check_rating("Correct")
    assert score == 1.0
    assert cat == "TRUE"

    score, cat = normalize_fact_check_rating("Mostly True")
    assert score == 0.85
    assert cat == "MOSTLY_TRUE"

    score, cat = normalize_fact_check_rating("Missing Context")
    assert score == 0.4
    assert cat == "MIXED"


def test_source_credibility_weighting():
    """Test domain authority scoring for accredited vs generic publishers."""
    reuters_score = compute_source_credibility("Reuters Fact Check")
    snopes_score = compute_source_credibility("Snopes.com")
    unknown_score = compute_source_credibility("Unknown Regional Blog")

    assert reuters_score >= 0.95
    assert snopes_score >= 0.95
    assert unknown_score == 0.70


# ==============================================================================
# 3. FULL PIPELINE WITH MOCKED API RESPONSES
# ==============================================================================

@pytest.mark.asyncio
async def test_evidence_verifier_contradicted_flow():
    """Test contradicted / debunked claim produces low score and CONTRADICTED status."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "The moon is made of green cheese.",
                "claimant": "Viral Meme",
                "claimReview": [
                    {
                        "publisher": {"name": "Snopes", "site": "snopes.com"},
                        "textualRating": "False",
                        "url": "https://snopes.com/factcheck/moon-cheese",
                    }
                ],
            }
        ],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("The moon is made of green cheese according to latest reports.")

    assert result["status"] == "CONTRADICTED"
    assert result["evidence_score"] == 0.0
    assert len(result["fact_checks"]) == 1
    assert "DEBUNKED_BY_FACT_CHECKERS" in result["flags"]
    assert "Snopes" in result["explanation"]


@pytest.mark.asyncio
async def test_evidence_verifier_supported_flow():
    """Test verified claim produces high score and SUPPORTED status."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "James Webb Space Telescope captures deepest image of universe.",
                "claimant": "NASA",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check", "site": "reuters.com"},
                        "textualRating": "True",
                        "url": "https://reuters.com/factcheck/jwst",
                    }
                ],
            }
        ],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("James Webb Space Telescope captures deepest image of universe.")

    assert result["status"] == "SUPPORTED"
    assert result["evidence_score"] == 100.0
    assert "VERIFIED_BY_FACT_CHECKERS" in result["flags"]


@pytest.mark.asyncio
async def test_evidence_verifier_no_fact_check_found_neutral_baseline():
    """Test that absence of fact-checks returns NO_FACT_CHECK_FOUND and neutral 50.0 score (NEVER assumes True)."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("Random obscure event happened on a local street yesterday.")

    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["evidence_score"] == 50.0  # Neutral baseline
    assert result["fact_checks"] == []
    assert "Absence of fact-checks does not verify or disprove" in result["explanation"]


@pytest.mark.asyncio
async def test_evidence_verifier_api_rate_limited_fallback():
    """Test API rate-limit returns neutral fallback with appropriate flag."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "RATE_LIMITED",
        "claims": [],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("A scientific report was published today.")

    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["evidence_score"] == 50.0
    assert "FACT_CHECK_API_RATE_LIMITED" in result["flags"]
