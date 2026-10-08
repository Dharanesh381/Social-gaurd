"""Production endpoint tests for POST /analyze.

Verifies:
- Complete execution of Modules 1-5 without database access or persistence.
- Validation of AnalysisRequest.
- Scenarios:
  1. valid post
  2. invalid post
  3. missing text
  4. no comments
  5. no media
  6. no fact-check API key
  7. API unavailable
  8. module partial failure
"""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.modules.evidence_verification.factcheck_client import fact_check_client


# ==============================================================================
# 1. VALID POST (Full E2E Pipeline)
# ==============================================================================

def test_analyze_valid_post(client: TestClient):
    """Test standard valid post executes all 5 modules and returns complete analysis JSON."""
    mock_fc = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "NASA rovers detect subsurface water ice reserves on Mars.",
                "claimant": "NASA JPL",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check", "site": "reuters.com"},
                        "textualRating": "True",
                        "url": "https://reuters.com/factcheck/mars-water",
                    }
                ],
            }
        ],
    })

    payload = {
        "request_id": "test_req_valid_001",
        "post": {
            "platform": "twitter",
            "post_id": "tw_1001",
            "text": "NASA rovers confirm detection of subsurface water ice reserves on Mars through deep radar soundings.",
            "timestamp": "2026-09-10T12:00:00Z",
            "hashtags": ["#Space", "#Mars", "#NASA"],
            "media": [
                {
                    "url": "https://example.com/mars_chart.png",
                    "media_type": "image",
                }
            ],
            "author": {
                "username": "science_reporter",
                "account_age_days": 1200.0,
                "followers_count": 24000,
                "following_count": 380,
                "posts_count": 3200,
                "recent_posts_frequency_per_day": 2.2,
                "recent_comments_frequency_per_day": 3.5,
                "duplicate_posts_ratio": 0.01,
                "hashtag_repetition_rate": 0.08,
                "average_engagement_rate": 0.045,
            },
            "comments": [
                {
                    "comment_id": "c1",
                    "text": "Incredible planetary science milestone if confirmed by independent teams! 🚀",
                    "author": {"username": "peer_reviewer"},
                    "likes": 12,
                },
                {
                    "comment_id": "c2",
                    "text": "The radar reflection dataset matches the orbital sounding signatures.",
                    "author": {"username": "astronomer_dan"},
                    "likes": 5,
                },
            ],
        },
    }

    with patch.object(fact_check_client, "search_claims", mock_fc):
        response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify top-level structure
    assert data["request_id"] == "test_req_valid_001"
    assert data["consolidated_score"] is not None
    assert data["classification"] in ("LIKELY REAL", "PROBABLY REAL")
    assert "explanation" in data
    assert "xai_explanation" in data
    assert "processing_timings" in data

    # Verify all 5 module results are populated
    assert "module_1" in data and data["module_1"]["status"] in ("COMPLETED", "PARTIAL")
    assert "module_2" in data and data["module_2"]["status"] in ("COMPLETED", "PARTIAL")
    assert "module_3" in data and data["module_3"]["status"] == "COMPLETED"
    assert "module_4" in data and data["module_4"]["status"] in ("COMPLETED", "PARTIAL")
    assert "module_5" in data and data["module_5"]["status"] in ("COMPLETED", "PARTIAL")

    # Verify XAI factors
    assert isinstance(data["xai_explanation"]["positive_factors"], list)
    assert isinstance(data["xai_explanation"]["negative_factors"], list)
    assert isinstance(data["xai_explanation"]["confidence_notes"], list)

    # Verify no unhandled errors
    assert data["errors"] == []


# ==============================================================================
# 2. INVALID POST (Schema Validation)
# ==============================================================================

def test_analyze_invalid_post_missing_post_object(client: TestClient):
    """Test rejection when post object is completely omitted."""
    response = client.post("/analyze", json={"request_id": "bad_req_001"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "ValidationError"


def test_analyze_invalid_post_negative_counts(client: TestClient):
    """Test rejection when numeric metrics violate schema boundaries."""
    payload = {
        "post": {
            "platform": "twitter",
            "text": "Some sample text",
            "author": {
                "username": "bot_user",
                "account_age_days": -10.0,  # Invalid: must be >= 0
            },
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422


# ==============================================================================
# 3. MISSING TEXT
# ==============================================================================

def test_analyze_missing_text_empty_string(client: TestClient):
    """Test rejection when post text is an empty string."""
    payload = {
        "post": {
            "platform": "twitter",
            "text": "",
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert any("text" in str(d) for d in data.get("details", []))


def test_analyze_missing_text_whitespace_only(client: TestClient):
    """Test rejection when post text consists solely of whitespace."""
    payload = {
        "post": {
            "platform": "twitter",
            "text": "   \n\t  ",
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 422


# ==============================================================================
# 4. NO COMMENTS
# ==============================================================================

def test_analyze_no_comments_graceful_handling(client: TestClient):
    """Test post with empty comments list completes gracefully with UNAVAILABLE status in Module 1."""
    payload = {
        "post": {
            "platform": "reddit",
            "text": "Observatory detects periodic flare in nearby star system.",
            "comments": [],
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["module_1"]["status"] == "UNAVAILABLE"
    assert data["module_1"]["comment_count"] == 0
    assert any("No comments provided" in w for w in data["warnings"])
    assert data["consolidated_score"] is not None


# ==============================================================================
# 5. NO MEDIA
# ==============================================================================

def test_analyze_no_media_graceful_handling(client: TestClient):
    """Test post with no media attachments evaluates text-only in Module 4 without errors."""
    payload = {
        "post": {
            "platform": "twitter",
            "text": "Solar wind speed increases following minor coronal mass ejection.",
            "media": [],
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["post_info"]["media_count"] == 0
    assert data["module_4"]["status"] in ("COMPLETED", "PARTIAL")
    assert data["consolidated_score"] is not None


# ==============================================================================
# 6. NO FACT-CHECK API KEY
# ==============================================================================

def test_analyze_no_fact_check_api_key(client: TestClient):
    """Test that when Google Fact Check API key is unconfigured, Module 2 falls back to neutral baseline."""
    mock_fc = AsyncMock(return_value={"claims": [], "status": "API_KEY_MISSING"})
    payload = {
        "post": {
            "platform": "twitter",
            "text": "Breakthrough announced in battery energy storage density.",
        }
    }
    with patch.object(fact_check_client, "search_claims", mock_fc):
        response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["module_2"]["status"] in ("COMPLETED", "PARTIAL")
    assert data["module_2"]["score"] == 50.0  # Neutral baseline
    assert "GOOGLE_FACT_CHECK_API_KEY_NOT_CONFIGURED" in data["module_2"]["flags"]
    assert data["consolidated_score"] is not None


# ==============================================================================
# 7. API UNAVAILABLE (External Service Outage)
# ==============================================================================

def test_analyze_fact_check_api_unavailable_external_outage(client: TestClient):
    """Test that when Google Fact Check Tools API times out or raises an error,

    Module 2 catches the exception and falls back to neutral baseline without failing the request.
    """
    mock_fc = AsyncMock(return_value={
        "claims": [],
        "status": "CONNECTION_ERROR",
    })

    payload = {
        "post": {
            "platform": "twitter",
            "text": "Breaking economic update claims inflation index decreased.",
        }
    }

    with patch.object(fact_check_client, "search_claims", mock_fc):
        response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Module 2 handles API unavailability gracefully
    assert data["module_2"]["status"] in ("COMPLETED", "PARTIAL")
    assert data["module_2"]["score"] == 50.0
    assert "FACT_CHECK_API_UNAVAILABLE" in data["module_2"]["flags"]
    assert data["consolidated_score"] is not None


# ==============================================================================
# 7b. API CRITICAL FAILURE / EXCEPTION (Graceful Error Recovery)
# ==============================================================================

def test_analyze_fact_check_api_exception_handled_gracefully(client: TestClient):
    """Test that when Google Fact Check client raises an unexpected exception,

    the orchestrator catches the exception, records ERROR status, and returns 200 OK.
    """
    mock_fc = AsyncMock(
        side_effect=Exception("HTTP 503 Service Unavailable: Google Fact Check Tools down")
    )

    payload = {
        "post": {
            "platform": "twitter",
            "text": "Breaking economic update claims inflation index decreased.",
        }
    }

    with patch.object(fact_check_client, "search_claims", mock_fc):
        response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["module_2"]["status"] == "ERROR"
    assert "HTTP 503 Service Unavailable" in data["module_2"]["error"]
    assert data["consolidated_score"] is not None


# ==============================================================================
# 8. MODULE PARTIAL FAILURE (Fault Tolerance)
# ==============================================================================

def test_analyze_module_partial_failure_does_not_crash_pipeline(client: TestClient):
    """Test that if an individual module raises an internal unhandled exception,

    the orchestrator sets the module status to ERROR, records the error diagnostic,
    and returns 200 OK with the remaining fused score.
    """
    with patch("app.modules.user_behaviour.analyzer.user_behaviour_analyzer.analyze",
               side_effect=RuntimeError("Simulated unexpected crash in Module 3")):
        payload = {
            "post": {
                "platform": "twitter",
                "text": "Sample verified scientific observation report.",
                "author": {
                    "username": "sample_user",
                    "account_age_days": 100,
                },
            }
        }

        response = client.post("/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Module 3 is marked as ERROR
        assert data["module_3"]["status"] == "ERROR"
        assert "Simulated unexpected crash in Module 3" in data["module_3"]["error"]

        # Errors list contains diagnostic
        assert any("Module 3" in err for err in data["errors"])

        # Entire response is still returned with fused score
        assert data["consolidated_score"] is not None
        assert data["classification"] is not None


# ==============================================================================
# 9. IN-MEMORY VERIFICATION (No Database, No Persistence, No Auth Required)
# ==============================================================================

def test_analyze_no_database_no_persistence_no_auth(client: TestClient):
    """Verify that POST /analyze executes entirely in memory without database, persistence, or auth."""
    # Ensure request succeeds without any Authorization header or session cookies
    payload = {
        "post": {
            "platform": "generic",
            "text": "Open access research preprint published in global repository.",
        }
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert "consolidated_score" in data
    assert "classification" in data
    assert "module_scores" in data
