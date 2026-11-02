"""Unit & Integration Tests for Fact-Check Data Caching Engine (Module 2)."""

import time
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.evidence_verification.analyzer import EvidenceVerifier
from app.modules.evidence_verification.cache import FactCheckCache, fact_check_cache
from app.modules.evidence_verification.factcheck_client import GoogleFactCheckClient, fact_check_client


# ==============================================================================
# 1. CORE CACHE UNIT TESTS
# ==============================================================================

def test_query_cache_hit_and_normalization():
    """Verify query caching, whitespace/case normalization, and hit counting."""
    cache = FactCheckCache(default_ttl_seconds=3600.0, max_entries=10)
    data = {
        "status": "SUCCESS",
        "claims": [{"text": "NASA discovers water ice on Mars", "claimant": "NASA JPL"}],
    }

    # Store with uppercase/whitespace
    cache.set_query("  NASA Discovers Water Ice ON Mars  ", data, language_code="en")

    # Retrieve with different casing/spacing
    retrieved = cache.get_query("nasa discovers water ice on mars", language_code="en")
    assert retrieved is not None
    assert retrieved["status"] == "SUCCESS"
    assert retrieved["cached"] is True
    assert len(retrieved["claims"]) == 1

    # Miss check
    miss = cache.get_query("unrelated claim about moon", language_code="en")
    assert miss is None

    stats = cache.stats()
    assert stats["query_hits"] == 1
    assert stats["query_misses"] == 1
    assert stats["query_cache_size"] == 1


def test_post_cache_fingerprinting():
    """Verify post-level caching using text, post_id, and images."""
    cache = FactCheckCache(default_ttl_seconds=3600.0, max_entries=10)
    post_text = "Drinking hot lemon water cures all viral infections immediately."
    m2_result = {
        "score": 0.0,
        "status": "CONTRADICTED",
        "claims": ["Drinking hot lemon water cures all viral infections immediately."],
        "fact_checks": [{"publisher": "Snopes", "rating": "False"}],
        "flags": ["DEBUNKED_BY_FACT_CHECKERS"],
    }

    cache.set_post(post_text=post_text, result=m2_result, post_id="post_999")

    # Retrieval by same text and post_id
    hit = cache.get_post(post_text=post_text, post_id="post_999")
    assert hit is not None
    assert hit["score"] == 0.0
    assert hit["status"] == "CONTRADICTED"
    assert hit["from_cache"] is True
    assert "FACT_CHECK_CACHE_HIT" in hit["flags"]

    # Retrieval by same text without post_id (fingerprint accounts for content)
    hit_content_only = cache.get_post(post_text=post_text)
    # Different post_id will produce different fingerprint if post_id was supplied
    assert hit_content_only is None

    stats = cache.stats()
    assert stats["post_hits"] == 1
    assert stats["post_misses"] == 1


def test_cache_ttl_expiration():
    """Verify expired cache entries are automatically evicted upon access."""
    cache = FactCheckCache(default_ttl_seconds=0.05, max_entries=10)  # 50ms TTL
    cache.set_query("Temporary Fact", {"claims": []}, ttl_seconds=0.05)

    # Immediate check should hit
    assert cache.get_query("Temporary Fact") is not None

    # Wait for TTL expiry
    time.sleep(0.06)
    assert cache.get_query("Temporary Fact") is None


def test_cache_lru_eviction():
    """Verify that exceeding max_entries evicts the least recently used entry."""
    cache = FactCheckCache(default_ttl_seconds=3600.0, max_entries=2)

    cache.set_query("claim_1", {"claims": [1]})
    cache.set_query("claim_2", {"claims": [2]})
    # Access claim_1 to make claim_2 the LRU item
    _ = cache.get_query("claim_1")

    # Add claim_3 (should evict claim_2)
    cache.set_query("claim_3", {"claims": [3]})

    assert cache.get_query("claim_1") is not None
    assert cache.get_query("claim_3") is not None
    assert cache.get_query("claim_2") is None


# ==============================================================================
# 2. FACT CHECK CLIENT CACHING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_fact_check_client_caches_api_calls():
    """Test that GoogleFactCheckClient does not call external network API on repeat query."""
    cache = FactCheckCache(default_ttl_seconds=3600.0)
    client = GoogleFactCheckClient(api_key="mock_test_key", cache=cache)

    mock_resp = {
        "status": "SUCCESS",
        "claims": [{"text": "Breaking news claim verified by Reuters", "claimant": "Reuters"}],
    }

    # Simulate the first call hitting external API
    with patch.object(client, "_get_client") as mock_http:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {"claims": mock_resp["claims"]}
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_http.return_value = mock_client_instance

        # Call 1: Cache Miss -> calls mock HTTP
        res1 = await client.search_claims("Breaking news claim verified by Reuters")
        assert res1["status"] == "SUCCESS"
        assert len(res1["claims"]) == 1
        assert mock_client_instance.get.call_count == 1

        # Call 2: Cache Hit -> MUST NOT call mock HTTP
        res2 = await client.search_claims("breaking news claim VERIFIED by reuters")
        assert res2["status"] == "SUCCESS"
        assert res2.get("cached") is True
        assert len(res2["claims"]) == 1
        # HTTP call count remains 1!
        assert mock_client_instance.get.call_count == 1


# ==============================================================================
# 3. EVIDENCE VERIFIER POST CACHING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_evidence_verifier_post_cache_avoids_api():
    """Test that EvidenceVerifier retrieves previous post result without calling search_claims."""
    cache = FactCheckCache(default_ttl_seconds=3600.0)
    mock_fc = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "Subsurface water ice confirmed on Mars.",
                "claimant": "NASA",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check", "site": "reuters.com"},
                        "textualRating": "True",
                        "url": "https://reuters.com/factcheck/mars-ice-test",
                    }
                ],
            }
        ],
    })

    client = GoogleFactCheckClient(api_key="mock_key", cache=cache)
    client.search_claims = mock_fc

    verifier = EvidenceVerifier(api_client=client, cache=cache)
    post_text = "NASA scientists confirm discovery of massive subsurface water ice reserves on Mars!"

    # First verification: Calls search_claims
    res1 = await verifier.verify(post_text=post_text, post_id="post_mars_001")
    assert res1["evidence_score"] == 100.0
    assert res1["status"] == "SUPPORTED"
    assert mock_fc.call_count >= 1
    first_call_count = mock_fc.call_count

    # Second verification of the SAME post: Cache Hit!
    res2 = await verifier.verify(post_text=post_text, post_id="post_mars_001")
    assert res2["evidence_score"] == 100.0
    assert res2["status"] == "SUPPORTED"
    assert res2.get("from_cache") is True
    assert "FACT_CHECK_CACHE_HIT" in res2["flags"]

    # search_claims was NOT called again!
    assert mock_fc.call_count == first_call_count


# ==============================================================================
# 4. END-TO-END /ANALYZE REPEAT VERIFICATION
# ==============================================================================

def test_e2e_repeat_post_analysis_uses_cached_evidence():
    """Verify that analyzing the same post twice through the FastAPI /analyze endpoint

    retrieves the cached fact-check data on the second attempt without re-calling the API.
    """
    mock_search = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "Drinking boiling bleach cures viruses.",
                "claimant": "Social Media",
                "claimReview": [
                    {
                        "publisher": {"name": "Snopes", "site": "snopes.com"},
                        "textualRating": "False",
                        "url": "https://snopes.com/factcheck/bleach",
                    }
                ],
            }
        ],
    })

    fact_check_client.search_claims = mock_search

    payload = {
        "post": {
            "platform": "twitter",
            "post_id": "repeat_test_post_777",
            "text": "Drinking boiling bleach completely cures all respiratory infections in 5 minutes!",
            "hashtags": ["#Bleach", "#HealthAlert"],
            "media": [],
            "author": {
                "username": "viral_health_news",
                "account_age_days": 100,
                "followers": 500,
                "following": 200,
            },
            "comments": [],
        }
    }

    test_client = TestClient(app)

    # 1. First analysis: executes fact check API
    resp1 = test_client.post("/analyze", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["module_scores"]["evidence_verification"] == 0.0
    assert data1["module_2"]["status"] in ("COMPLETED", "PARTIAL")
    initial_api_calls = mock_search.call_count
    assert initial_api_calls >= 1

    # 2. Second analysis of the EXACT SAME post:
    # Must retrieve cached fact check data without calling API again!
    resp2 = test_client.post("/analyze", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Evidence score matches previous result
    assert data2["module_scores"]["evidence_verification"] == 0.0
    # Module 2 output indicates it was retrieved from cache
    assert data2["module_2"]["cached"] is True
    assert "FACT_CHECK_CACHE_HIT" in data2["module_2"]["flags"]

    # Verify search_claims was NOT called again on second attempt!
    assert mock_search.call_count == initial_api_calls
