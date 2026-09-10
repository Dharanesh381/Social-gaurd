"""End-to-End Integration tests for POST /analyze with live analytical pipeline."""

from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.modules.evidence_verification.factcheck_client import fact_check_client


def test_analyze_realistic_sample_post_end_to_end(client: TestClient):
    """Test realistic social media post verification with live ML modules,

    mocked Google Fact Check API, and full explainability synthesis.
    """
    # Mock Google Fact Check response for controlled deterministic assertions
    fact_check_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "NASA rovers detect water ice reserves beneath Martian surface.",
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
        "request_id": "sg_integration_req_001",
        "post": {
            "platform": "twitter",
            "text": "NASA rovers confirm detection of water ice reserves beneath the Martian surface during deep radar soundings.",
            "hashtags": ["#Space", "#Mars", "#NASA"],
            "media": [
                {
                    "url": "https://example.com/mars_chart.png",
                    "media_type": "image",
                }
            ],
            "timestamp": "2026-09-10T09:00:00Z",
            "author": {
                "username": "science_reporter",
                "account_age_days": 1200,
                "followers": 15000,
                "following": 450,
                "posts_per_day": 2.5,
                "comments_per_day": 4.0,
                "engagement_rate": 0.045,
                "duplicate_content_ratio": 0.01,
                "hashtag_repetition_rate": 0.10,
            },
            "comments": [
                {
                    "comment_id": "c_1",
                    "text": "Fascinating data! Does this correlate with earlier orbital radar measurements?",
                    "timestamp": "2026-09-10T09:10:00Z",
                    "likes": 5,
                    "emojis": ["🚀"],
                },
                {
                    "comment_id": "c_2",
                    "text": "Incredible step forward for planetary geology exploration.",
                    "timestamp": "2026-09-10T09:25:00Z",
                    "likes": 2,
                    "emojis": ["👏"],
                },
            ],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # 1. Core Top-Level Outputs
    assert data["request_id"] == "sg_integration_req_001"
    assert data["consolidated_score"] is not None
    assert data["consolidated_score"] >= 80.0
    assert data["classification"] == "LIKELY REAL"
    assert data["ai_generation_probability"] is not None

    # 2. Module Scores Breakdown
    scores = data["module_scores"]
    assert scores["comment_analysis"] >= 70.0
    assert scores["evidence_verification"] == 100.0  # From Reuters Fact Check True rating
    assert scores["user_behaviour"] >= 80.0
    assert scores["similar_content"] is not None

    # 3. Explainability & Diagnostics
    explanation = data["explanation"]
    assert "LIKELY REAL" in explanation

    results_data = data["module_results"]
    assert "timings_ms" in results_data
    assert "comment_analysis_ms" in results_data["timings_ms"]
    assert "evidence_verification_ms" in results_data["timings_ms"]
    assert "user_behaviour_ms" in results_data["timings_ms"]
    assert "similar_content_ms" in results_data["timings_ms"]
    assert "score_fusion_ms" in results_data["timings_ms"]
    assert "total_pipeline_ms" in results_data["timings_ms"]

    xai_data = results_data["explainability"]
    assert len(xai_data["positive_factors"]) >= 2
    assert "Reuters Fact Check" in str(xai_data["positive_factors"])


def test_analyze_invalid_payload_missing_post(client: TestClient):
    """Test schema validation rejection when post object is omitted."""
    response = client.post("/analyze", json={"request_id": "bad_req"})
    assert response.status_code == 422
