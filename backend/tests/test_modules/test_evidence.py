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


def test_claim_extractor_filters_questions():
    """Test extractor filters out questions and interrogatives."""
    extractor = SimpleClaimExtractor()
    text = "Why did the price of Bitcoin fluctuate so wildly yesterday? Can anyone explain this?"
    claims = extractor.extract_claims(text)
    assert claims == []
    assert extractor.classify_filtered_reason(text) == "QUESTION"


def test_claim_extractor_filters_greetings():
    """Test extractor filters out greetings and pleasantries."""
    extractor = SimpleClaimExtractor()
    text = "Good morning everyone! Have a wonderful day ahead!"
    claims = extractor.extract_claims(text)
    assert claims == []
    assert extractor.classify_filtered_reason(text) == "GREETING"


def test_claim_extractor_empty_text():
    """Test claim extraction on empty or whitespace strings."""
    extractor = SimpleClaimExtractor()
    assert extractor.extract_claims("") == []
    assert extractor.extract_claims("   \n\t  ") == []
    assert extractor.classify_filtered_reason("") == "EMPTY"


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

    score, cat = normalize_fact_check_rating("Partially True")
    assert score == 0.55
    assert cat == "MIXED"

    score, cat = normalize_fact_check_rating("Missing Context")
    assert score == 0.4
    assert cat == "MIXED"


def test_source_credibility_weighting():
    """Test domain authority scoring for accredited vs generic publishers."""
    reuters_score = compute_source_credibility("Reuters Fact Check")
    snopes_score = compute_source_credibility("Snopes.com")
    politifact_score = compute_source_credibility("PolitiFact")
    unknown_score = compute_source_credibility("Unknown Regional Blog")

    assert reuters_score >= 0.98
    assert snopes_score >= 0.95
    assert politifact_score >= 0.95
    assert unknown_score == 0.70


# ==============================================================================
# 3. REQUIRED MODULE 2 PIPELINE VERIFICATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_true_claim():
    """1. True claim: verified by accredited fact-checker -> High score & SUPPORTED."""
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

    assert result["score"] == 100.0
    assert result["evidence_score"] == 100.0
    assert result["status"] == "SUPPORTED"
    assert result["verified_count"] == 1
    assert result["false_count"] == 0
    assert result["unverified_count"] == 0
    assert result["source_quality"] >= 0.95
    assert len(result["claims"]) >= 1
    assert len(result["fact_checks"]) == 1
    assert "VERIFIED_BY_FACT_CHECKERS" in result["flags"]
    assert "Reuters" in result["explanation"]
    assert "supported" in result["explanation"].lower() or "verified" in result["explanation"].lower()


@pytest.mark.asyncio
async def test_false_claim():
    """2. False claim: debunked by accredited fact-checker -> Score 0.0 & CONTRADICTED."""
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

    assert result["score"] == 0.0
    assert result["evidence_score"] == 0.0
    assert result["status"] == "CONTRADICTED"
    assert result["verified_count"] == 0
    assert result["false_count"] == 1
    assert result["unverified_count"] == 0
    assert result["source_quality"] >= 0.95
    assert len(result["claims"]) >= 1
    assert len(result["fact_checks"]) == 1
    assert "DEBUNKED_BY_FACT_CHECKERS" in result["flags"]
    assert "Snopes" in result["explanation"]
    assert "debunked" in result["explanation"].lower() or "contradicted" in result["explanation"].lower()


@pytest.mark.asyncio
async def test_partially_true_claim():
    """3. Partially true claim: rated partially true -> ~55 score & MIXED/MISLEADING status."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "New economic bill cut deficit in half during fiscal year 2023.",
                "claimant": "Government Spokesperson",
                "claimReview": [
                    {
                        "publisher": {"name": "PolitiFact", "site": "politifact.com"},
                        "textualRating": "Partially True",
                        "url": "https://politifact.com/factchecks/deficit-cut",
                    }
                ],
            }
        ],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("New economic bill cut deficit in half during fiscal year 2023.")

    assert 45.0 <= result["score"] <= 65.0
    assert result["status"] == "MIXED/MISLEADING"
    assert result["verified_count"] == 0
    assert result["false_count"] == 0
    assert result["unverified_count"] == 0
    assert result["source_quality"] >= 0.90
    assert len(result["fact_checks"]) == 1
    assert "PARTIALLY_TRUE_CLAIM" in result["flags"]
    assert "partially true" in result["explanation"].lower() or "missing" in result["explanation"].lower()


@pytest.mark.asyncio
async def test_unindexed_claim():
    """4. Unindexed claim: NO fact-check result MUST NOT automatically mean false -> Neutral 50.0."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("A new independent coffee roaster opened on 8th Avenue yesterday.")

    assert result["score"] == 50.0  # CRITICAL RULE: Neutral baseline!
    assert result["evidence_score"] == 50.0
    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["verified_count"] == 0
    assert result["false_count"] == 0
    assert result["unverified_count"] == 1
    assert result["source_quality"] == 0.0
    assert result["fact_checks"] == []
    assert "UNINDEXED_CLAIM" in result["flags"]
    assert "Absence of fact-checks does not verify or disprove" in result["explanation"]


@pytest.mark.asyncio
async def test_opinion():
    """5. Opinion: filtered out from fact-checking -> Neutral 50.0 & OPINION_DETECTED."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock()

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("In my opinion, this new movie is completely overrated and boring.")

    assert result["score"] == 50.0
    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["claims"] == []
    assert result["fact_checks"] == []
    assert result["verified_count"] == 0
    assert result["false_count"] == 0
    assert result["unverified_count"] == 0
    assert result["source_quality"] == 0.0
    assert "OPINION_DETECTED" in result["flags"]
    assert "NO_VERIFIABLE_CLAIMS_DETECTED" in result["flags"]
    assert "opinions" in result["explanation"].lower()
    mock_client.search_claims.assert_not_called()


@pytest.mark.asyncio
async def test_question():
    """6. Question: filtered out from fact-checking -> Neutral 50.0 & QUESTION_DETECTED."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock()

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("Why did the stock market drop so drastically today, and will it recover?")

    assert result["score"] == 50.0
    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["claims"] == []
    assert result["fact_checks"] == []
    assert result["verified_count"] == 0
    assert result["false_count"] == 0
    assert result["unverified_count"] == 0
    assert result["source_quality"] == 0.0
    assert "QUESTION_DETECTED" in result["flags"]
    assert "NO_VERIFIABLE_CLAIMS_DETECTED" in result["flags"]
    assert "questions" in result["explanation"].lower()
    mock_client.search_claims.assert_not_called()


@pytest.mark.asyncio
async def test_api_unavailable():
    """7. API unavailable: connection error or 5xx -> Graceful neutral fallback 50.0."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "CONNECTION_ERROR",
        "claims": [],
        "error": "Connection to API failed",
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("NASA announced plans for a crewed Mars landing in 2035.")

    assert result["score"] == 50.0
    assert result["evidence_score"] == 50.0
    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["verified_count"] == 0
    assert result["false_count"] == 0
    assert result["unverified_count"] == 1
    assert result["source_quality"] == 0.0
    assert "FACT_CHECK_API_UNAVAILABLE" in result["flags"]
    assert "unavailable" in result["explanation"].lower()


@pytest.mark.asyncio
async def test_missing_api_key():
    """8. Missing API key: unconfigured key -> Graceful neutral fallback 50.0."""
    client_no_key = GoogleFactCheckClient(api_key="")
    verifier = EvidenceVerifier(api_client=client_no_key)
    result = await verifier.verify("Archaeologists discovered an ancient temple beneath the ruins.")

    assert result["score"] == 50.0
    assert result["evidence_score"] == 50.0
    assert result["status"] == "NO_FACT_CHECK_FOUND"
    assert result["verified_count"] == 0
    assert result["false_count"] == 0
    assert result["unverified_count"] == 1
    assert result["source_quality"] == 0.0
    assert "GOOGLE_FACT_CHECK_API_KEY_NOT_CONFIGURED" in result["flags"]
    assert "not configured" in result["explanation"].lower()


@pytest.mark.asyncio
async def test_multiple_fact_check_results_aggregation():
    """Test aggregation of multiple fact-check reviews with publisher authority weighting."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "Global climate agreement ratified by 190 nations.",
                "claimant": "UN News",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check", "site": "reuters.com"},
                        "textualRating": "True",
                        "url": "https://reuters.com/factcheck/un-climate",
                    },
                    {
                        "publisher": {"name": "Snopes", "site": "snopes.com"},
                        "textualRating": "Correct",
                        "url": "https://snopes.com/factcheck/climate-deal",
                    },
                ],
            }
        ],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("Global climate agreement ratified by 190 nations.")

    assert result["score"] == 100.0
    assert result["status"] == "SUPPORTED"
    assert result["verified_count"] == 2
    assert result["false_count"] == 0
    assert len(result["fact_checks"]) == 2
    assert result["source_quality"] >= 0.95
    assert "Reuters Fact Check" in result["explanation"]
    assert "Snopes" in result["explanation"]


@pytest.mark.asyncio
async def test_conflicting_fact_check_results():
    """Test handling of conflicting fact-check reviews across different publishers."""
    mock_client = GoogleFactCheckClient(api_key="test_key")
    mock_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "New tax law disproportionately impacts middle income families.",
                "claimant": "Political Campaign",
                "claimReview": [
                    {
                        "publisher": {"name": "Associated Press", "site": "apnews.com"},
                        "textualRating": "True",
                        "url": "https://apnews.com/ap-fact-check/tax-law",
                    },
                    {
                        "publisher": {"name": "Full Fact", "site": "fullfact.org"},
                        "textualRating": "False",
                        "url": "https://fullfact.org/tax-law-check",
                    },
                ],
            }
        ],
    })

    verifier = EvidenceVerifier(api_client=mock_client)
    result = await verifier.verify("New tax law disproportionately impacts middle income families.")

    assert result["status"] == "MIXED/MISLEADING"
    assert result["verified_count"] == 1
    assert result["false_count"] == 1
    assert "CONFLICTING_FACT_CHECK_REVIEWS" in result["flags"]
