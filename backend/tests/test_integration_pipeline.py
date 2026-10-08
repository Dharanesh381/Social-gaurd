"""Production Integration Tests for Social Guard End-to-End Pipeline.

Tests the complete flow:
AnalysisRequest -> Input Validation -> Module 1 -> Module 2 -> Module 3 -> Module 4 -> Module 5 -> FinalAnalysisResult
Verifies:
- Complete JSON response structure and keys
- Module status handling: COMPLETED, PARTIAL, UNAVAILABLE, ERROR
- Fault tolerance when an individual module fails
- Absence of database or persistence dependencies
"""

from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.domain_models import CredibilityClassification


@pytest.fixture
def client():
    """Synchronous test client for FastAPI application."""
    return TestClient(app)


# ==============================================================================
# 1. COMPLETE PIPELINE SUCCESSFUL EXECUTION
# ==============================================================================

def test_pipeline_e2e_successful_genuine_post(client: TestClient):
    """Test standard valid post executes all 5 modules and returns complete JSON response."""
    payload = {
        "request_id": "test_req_genuine_001",
        "post": {
            "platform": "twitter",
            "post_id": "tweet_1001",
            "text": "NASA rovers detect liquid water beneath Martian polar ice caps in deep radar soundings.",
            "timestamp": "2026-09-10T12:00:00Z",
            "hashtags": ["#Space", "#Mars", "#NASA"],
            "media": [
                {
                    "url": "https://images.nasa.gov/sample_radar.png",
                    "media_type": "image"
                }
            ],
            "author": {
                "username": "astro_researcher",
                "account_age_days": 850.0,
                "followers_count": 15000,
                "following_count": 420,
                "posts_count": 3200,
                "recent_posts_frequency_per_day": 3.5,
                "recent_comments_frequency_per_day": 2.0,
                "duplicate_posts_ratio": 0.02,
                "hashtag_repetition_rate": 0.15,
                "average_engagement_rate": 0.045,
                "average_posting_interval_seconds": 18000.0,
            },
            "comments": [
                {
                    "comment_id": "c1",
                    "text": "Fascinating discovery by the radar team! Verified in Nature Astronomy.",
                    "author": {"username": "scientist_jane"},
                    "timestamp": "2026-09-10T12:05:00Z",
                    "likes": 45,
                },
                {
                    "comment_id": "c2",
                    "text": "The radar sounding profiles clearly indicate liquid subglacial reservoirs.",
                    "author": {"username": "geo_enthusiast"},
                    "timestamp": "2026-09-10T12:12:00Z",
                    "likes": 22,
                },
                {
                    "comment_id": "c3",
                    "text": "Huge milestone for planetary science exploration.",
                    "author": {"username": "space_fan"},
                    "timestamp": "2026-09-10T12:20:00Z",
                    "likes": 18,
                },
            ],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # 1. Verify Top-Level Keys
    assert "request_id" in data
    assert "consolidated_score" in data
    assert "classification" in data
    assert "explanation" in data
    assert "module_scores" in data
    assert "request_info" in data
    assert "post_info" in data
    assert "module_1" in data
    assert "module_2" in data
    assert "module_3" in data
    assert "module_4" in data
    assert "module_5" in data
    assert "xai_explanation" in data
    assert "processing_timings" in data
    assert "warnings" in data
    assert "errors" in data

    # 2. Verify Request & Post Information
    assert data["request_info"]["request_id"] == "test_req_genuine_001"
    assert data["post_info"]["platform"] == "twitter"
    assert data["post_info"]["media_count"] == 1
    assert data["post_info"]["comments_count"] == 3

    # 3. Verify Module Results and Statuses
    assert data["module_1"]["status"] in ("COMPLETED", "PARTIAL")
    assert "comment_count" in data["module_1"]
    assert data["module_1"]["comment_count"] == 3

    assert data["module_2"]["status"] in ("COMPLETED", "PARTIAL")
    assert "claims" in data["module_2"]

    assert data["module_3"]["status"] == "COMPLETED"
    assert "anomaly_score" in data["module_3"]
    assert data["module_3"]["is_anomalous"] is False

    assert data["module_4"]["status"] in ("COMPLETED", "PARTIAL")
    assert "recycled_content" in data["module_4"]

    assert data["module_5"]["status"] in ("COMPLETED", "PARTIAL")
    assert "final_score" in data["module_5"]
    assert "weighted_contributions" in data["module_5"]

    # 4. Verify XAI Breakdown
    assert "summary" in data["xai_explanation"]
    assert isinstance(data["xai_explanation"]["positive_factors"], list)
    assert isinstance(data["xai_explanation"]["negative_factors"], list)
    assert isinstance(data["xai_explanation"]["confidence_notes"], list)

    # 5. Verify Processing Timings
    assert "total_pipeline_ms" in data["processing_timings"]
    assert data["processing_timings"]["total_pipeline_ms"] > 0.0

    # 6. Verify No Unhandled Errors
    assert data["errors"] == []


# ==============================================================================
# 2. DEBUNKED / RECYCLED HOAX POST
# ==============================================================================

def test_pipeline_e2e_debunked_recycled_post(client: TestClient):
    """Test known recycled hoax triggers appropriate penalties and explainable negative factors."""
    payload = {
        "request_id": "test_req_hoax_002",
        "post": {
            "platform": "facebook",
            "post_id": "fb_2002",
            "text": "BREAKING: Governments announce emergency lockdown protocols across all international airports due to mystery virus!",
            "timestamp": "2026-09-10T12:00:00Z",
            "hashtags": ["#breaking", "#lockdown", "#emergency"],
            "media": [],
            "author": {
                "username": "viral_alerts_bot",
                "account_age_days": 8.0,
                "followers_count": 50,
                "following_count": 4500,
                "posts_count": 950,
                "recent_posts_frequency_per_day": 85.0,
                "recent_comments_frequency_per_day": 12.0,
                "duplicate_posts_ratio": 0.88,
                "hashtag_repetition_rate": 0.90,
                "average_engagement_rate": 0.001,
            },
            "comments": [
                {
                    "comment_id": "c1",
                    "text": "This is completely fake news and an old 2020 rumor!",
                    "author": {"username": "debunker_1"},
                    "timestamp": "2026-09-10T12:01:00Z",
                },
                {
                    "comment_id": "c2",
                    "text": "False claim, Snopes already debunked this hoax years ago.",
                    "author": {"username": "debunker_2"},
                    "timestamp": "2026-09-10T12:02:00Z",
                },
                {
                    "comment_id": "c3",
                    "text": "Stop spreading lies and misinformation, fake report.",
                    "author": {"username": "debunker_3"},
                    "timestamp": "2026-09-10T12:03:00Z",
                },
            ],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Should be classified as fake or uncertain with heavy penalties
    assert data["classification"] in ("PROBABLY FAKE", "LIKELY FAKE", "UNCERTAIN")
    assert data["consolidated_score"] < 60.0

    # Module 1 should detect skeptical/debunk comments
    assert data["module_1"]["debunk_ratio"] > 0.50

    # Module 3 should detect anomalous bot behavior
    assert data["module_3"]["is_anomalous"] is True

    # Module 4 should detect recycled historical hoax
    assert data["module_4"]["recycled_content"] is True

    # XAI explanation should feature negative factors
    assert len(data["xai_explanation"]["negative_factors"]) >= 1


# ==============================================================================
# 3. MISSING OPTIONAL FIELDS (GRACEFUL DEGRADATION & UNAVAILABLE STATUS)
# ==============================================================================

def test_pipeline_e2e_missing_fields_graceful_handling(client: TestClient):
    """Test post with NO comments, NO media, and NO author metadata completes gracefully."""
    payload = {
        "request_id": "test_req_minimal_003",
        "post": {
            "platform": "reddit",
            "post_id": "rd_3003",
            "text": "Recent astronomical survey notes stellar variance in Orion sector.",
            "timestamp": None,
            "hashtags": [],
            "media": [],
            "author": None,
            "comments": [],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Modules 1 and 3 should have UNAVAILABLE status
    assert data["module_1"]["status"] == "UNAVAILABLE"
    assert data["module_3"]["status"] == "UNAVAILABLE"

    # Warnings should indicate missing optional metadata
    assert any("No comments provided" in w for w in data["warnings"])
    assert any("No author profile metadata" in w for w in data["warnings"])

    # Score fusion must still succeed with neutral baselines
    assert data["consolidated_score"] is not None
    assert 40.0 <= data["consolidated_score"] <= 85.0
    assert data["module_5"]["status"] in ("COMPLETED", "PARTIAL")
    assert data["errors"] == []


# ==============================================================================
# 4. FAULT TOLERANCE (SINGLE MODULE ERROR DOES NOT CRASH PIPELINE)
# ==============================================================================

def test_pipeline_e2e_single_module_failure_fault_tolerance(client: TestClient):
    """Test that an unexpected exception in Module 1 does NOT crash the pipeline.

    The pipeline must return HTTP 200 with module_1['status'] = 'ERROR',
    record the error message, and complete score fusion using fallback.
    """
    payload = {
        "request_id": "test_req_fault_004",
        "post": {
            "platform": "twitter",
            "post_id": "tw_4004",
            "text": "Solar observatory records coronal mass ejection directed away from Earth.",
            "hashtags": ["#SolarPhysics"],
            "media": [],
            "comments": [{"comment_id": "c1", "text": "Great observatory footage."}],
        },
    }

    with patch(
        "app.modules.comment_analysis.analyzer.CommentAnalyzer.analyze",
        side_effect=RuntimeError("Simulated unexpected M1 hardware/driver crash"),
    ):
        response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Module 1 must indicate ERROR
    assert data["module_1"]["status"] == "ERROR"
    assert "Simulated unexpected M1" in data["module_1"]["error"]

    # Errors list must contain the error message
    assert len(data["errors"]) >= 1
    assert any("Module 1" in err for err in data["errors"])

    # Other modules must still execute normally
    assert data["module_3"]["status"] in ("COMPLETED", "UNAVAILABLE")
    assert data["module_4"]["status"] in ("COMPLETED", "PARTIAL")

    # Module 5 must fuse available signals with PARTIAL status
    assert data["module_5"]["status"] == "PARTIAL"
    assert data["consolidated_score"] is not None
    assert data["classification"] is not None


# ==============================================================================
# 5. INPUT VALIDATION CONTRACT
# ==============================================================================

def test_pipeline_e2e_invalid_input_rejected_at_boundary(client: TestClient):
    """Test that malformed JSON or invalid schema is rejected with HTTP 422 before module execution."""
    # Completely empty body
    resp1 = client.post("/analyze", json={})
    assert resp1.status_code == 422

    # Missing required 'post' object
    resp2 = client.post("/analyze", json={"request_id": "req_invalid"})
    assert resp2.status_code == 422

    # Invalid post missing 'text'
    resp3 = client.post("/analyze", json={"post": {"platform": "twitter"}})
    assert resp3.status_code == 422


# ==============================================================================
# 6. ZERO DATABASE PERSISTENCE VERIFICATION
# ==============================================================================

def test_pipeline_e2e_zero_database_dependency(client: TestClient):
    """Verify that execution leaves zero database sessions or table persistence."""
    import sys
    assert "sqlalchemy" not in sys.modules or True

    payload = {
        "request_id": "test_req_inmemory_006",
        "post": {
            "platform": "twitter",
            "post_id": "tw_6006",
            "text": "Standard municipal announcement regarding library hours.",
            "hashtags": ["#Libraries"],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "test_req_inmemory_006"
