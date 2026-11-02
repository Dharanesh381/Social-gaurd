"""
UI & Extension Contract Tests for Social Guard Extension.

Simulates the three mandatory UI test states:
1. Likely Real Preset Flow
2. Uncertain / Unverified Preset Flow
3. Likely Fake Preset Flow
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.main import app
from app.modules.evidence_verification.factcheck_client import fact_check_client


client = TestClient(app)


def test_ui_preset_likely_real_flow():
    """Test the 'Likely Real' preset verification payload."""
    fact_check_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "NASA rovers detect subsurface water ice reserves on Mars.",
                "claimant": "NASA JPL",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check", "site": "reuters.com"},
                        "textualRating": "True",
                        "url": "https://reuters.com/factcheck/mars-ice",
                    }
                ],
            }
        ],
    })

    payload = {
        "post": {
            "platform": "twitter",
            "text": "NASA planetary science rovers confirm detection of subsurface water ice reserves on Mars through deep radar soundings. #Space #Mars #NASA",
            "hashtags": ["#Space", "#Mars", "#NASA"],
            "media": [{"url": "https://example.com/mars_chart.png", "media_type": "image"}],
            "author": {
                "username": "science_reporter",
                "account_age_days": 1400,
                "followers": 24000,
                "following": 380,
                "posts_per_day": 2.2,
                "comments_per_day": 3.5,
                "engagement_rate": 0.045,
                "duplicate_content_ratio": 0.01,
                "hashtag_repetition_rate": 0.08,
            },
            "comments": [
                {"comment_id": "c_r1", "text": "Incredible discovery if confirmed by independent peer review! 🚀", "likes": 12, "emojis": ["🚀"]},
                {"comment_id": "c_r2", "text": "Does this match the earlier radar reflection datasets?", "likes": 5, "emojis": []},
            ],
        }
    }

    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["classification"] in ["LIKELY REAL", "PROBABLY REAL"]
    assert data["consolidated_score"] >= 75.0
    assert data["module_scores"]["evidence_verification"] == 100.0
    assert "reasons" in data["explanation"] or len(data["explanation"]) > 10


def test_ui_preset_uncertain_flow():
    """Test the 'Uncertain' preset verification payload."""
    fact_check_client.search_claims = AsyncMock(return_value={"status": "NO_FACT_CHECK_FOUND", "claims": []})

    payload = {
        "post": {
            "platform": "reddit",
            "text": "Local researchers claim to have created a stable room-temperature superconductor in a prototype laboratory setup.",
            "hashtags": ["#Physics", "#Superconductor"],
            "media": [],
            "author": {
                "username": "curious_physicist",
                "account_age_days": 650,
                "followers": 320,
                "following": 190,
                "posts_per_day": 1.1,
                "comments_per_day": 2.0,
                "engagement_rate": 0.03,
                "duplicate_content_ratio": 0.02,
                "hashtag_repetition_rate": 0.05,
            },
            "comments": [
                {"comment_id": "c_u1", "text": "Exciting if true, but we need independent lab replication before celebrating.", "likes": 7, "emojis": []}
            ],
        }
    }

    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["classification"] in ["UNCERTAIN", "PROBABLY REAL"]
    assert 40.0 <= data["consolidated_score"] <= 75.0
    assert data["module_scores"]["evidence_verification"] == 50.0  # Neutral baseline


def test_ui_preset_likely_fake_flow():
    """Test the 'Likely Fake' preset verification payload."""
    fact_check_client.search_claims = AsyncMock(return_value={
        "status": "SUCCESS",
        "claims": [
            {
                "text": "Drinking boiling bleach completely cures viral infections.",
                "claimant": "Social Media Posts",
                "claimReview": [
                    {
                        "publisher": {"name": "Snopes", "site": "snopes.com"},
                        "textualRating": "False / Dangerous Hoax",
                        "url": "https://snopes.com/factcheck/bleach-hoax",
                    }
                ],
            }
        ],
    })

    payload = {
        "post": {
            "platform": "facebook",
            "text": "BREAKING: Drinking boiling bleach completely cures all respiratory viral infections in 5 minutes! Share to save lives! #MiracleCure #HealthAlert",
            "hashtags": ["#MiracleCure", "#HealthAlert"],
            "media": [],
            "author": {
                "username": "super_cure_blast_bot",
                "account_age_days": 1,
                "followers": 2,
                "following": 4800,
                "posts_per_day": 450.0,
                "comments_per_day": 650.0,
                "engagement_rate": 0.0001,
                "duplicate_content_ratio": 0.96,
                "hashtag_repetition_rate": 0.92,
            },
            "comments": [
                {"comment_id": "c_f1", "text": "BUY THE BLEACH MIRACLE PROTOCOL NOW AT WWW.SCAM-CURE.FAKE 💊🚨", "likes": 0, "emojis": ["💊", "🚨"]},
                {"comment_id": "c_f2", "text": "BUY THE BLEACH MIRACLE PROTOCOL NOW AT WWW.SCAM-CURE.FAKE 💊🚨", "likes": 0, "emojis": ["💊", "🚨"]},
            ],
        }
    }

    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["classification"] in ["LIKELY FAKE", "PROBABLY FAKE"]
    assert data["consolidated_score"] < 40.0
    assert data["module_scores"]["evidence_verification"] == 0.0
    assert data["module_scores"]["user_behaviour"] < 40.0


def test_ui_preset_recycled_hoax_flow():
    """Test the 'Recycled Hoax' preset verification payload."""
    fact_check_client.search_claims = AsyncMock(return_value={"status": "NO_FACT_CHECK_FOUND", "claims": []})

    payload = {
        "post": {
            "platform": "facebook",
            "text": "BREAKING: Emergency nationwide lockdown declared tonight across all major international airports due to unknown airborne pathogen outbreak! Stock up immediately!",
            "hashtags": ["#BreakingNews", "#Lockdown", "#Emergency"],
            "media": [],
            "author": {
                "username": "viral_alerts_page",
                "account_age_days": 12,
                "followers": 85,
                "following": 3400,
                "posts_per_day": 95.0,
                "comments_per_day": 40.0,
                "engagement_rate": 0.002,
                "duplicate_content_ratio": 0.85,
                "hashtag_repetition_rate": 0.90,
            },
            "comments": [
                {"comment_id": "c_rec1", "text": "This is completely fake news and an old 2020 rumor! Stop lying.", "likes": 92, "emojis": []},
            ],
        }
    }

    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    m4 = data["module_4"]
    assert m4["recycled_content"] is True
    assert "RECYCLED_HISTORICAL_CONTENT_DETECTED" in m4["flags"]
    assert data["consolidated_score"] < 50.0


def test_ui_preset_ai_factual_flow():
    """Test the 'AI Factual' preset verification payload.

    Verifies the CRITICAL DESIGN PRINCIPLE:
    High AI generation probability (orthogonal dimension) does NOT degrade the factual credibility score.
    """
    fact_check_client.search_claims = AsyncMock(return_value={"status": "NO_FACT_CHECK_FOUND", "claims": []})

    payload = {
        "post": {
            "platform": "twitter",
            "text": "Comprehensive analysis confirms that the James Webb Space Telescope has successfully captured high-resolution transmission spectra of exoplanet WASP-96b, highlighting the detailed atmospheric composition and water vapor signatures across the planetary spectrum.",
            "hashtags": ["#JWST", "#Exoplanets", "#Astronomy"],
            "media": [
                {"url": "https://example.com/wasp96b_spectrum.png", "media_type": "image"}
            ],
            "author": {
                "username": "astro_briefs",
                "account_age_days": 900,
                "followers": 18500,
                "following": 220,
                "posts_per_day": 3.0,
                "comments_per_day": 4.0,
                "engagement_rate": 0.05,
                "duplicate_content_ratio": 0.02,
                "hashtag_repetition_rate": 0.10,
            },
            "comments": [
                {"comment_id": "c_ai1", "text": "Incredible spectral fidelity from NIRISS instrument!", "likes": 34, "emojis": []}
            ],
        }
    }

    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # AI probability is high (orthogonal detection)
    assert data["ai_generation_probability"] is not None
    assert data["ai_generation_probability"] >= 0.70  # >= 70% Synthetic

    # Credibility score remains solid (not penalized purely for being AI-generated)
    assert data["consolidated_score"] >= 50.0


