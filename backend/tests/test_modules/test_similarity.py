"""Unit tests for Module 4: Similar Content & Hashtag Analysis Engine."""

from datetime import datetime, timezone
import pytest

from app.modules.similar_content.analyzer import SimilarContentAnalyzer
from app.modules.similar_content.content_repository import (
    HistoricalContentItem,
    InMemoryContentRepository,
)
from app.modules.similar_content.hashtag_keyword import (
    compute_jaccard_similarity,
    extract_hashtags,
    extract_keywords,
)
from app.modules.similar_content.perceptual_hash import (
    calculate_hash_hamming_distance,
    hash_distance_to_similarity,
)


# ==============================================================================
# 1. HASHTAG, KEYWORD & HASH UTILITY TESTS
# ==============================================================================

def test_extract_hashtags_and_keywords():
    """Test hashtag and keyword tokenization and stopword removal."""
    text = "Breaking report on #Mars water! Scientists from NASA publish new data. #Space"
    hashtags = extract_hashtags(text, ["#Science", "mars"])
    assert "#mars" in hashtags
    assert "#space" in hashtags
    assert "#science" in hashtags

    keywords = extract_keywords(text)
    assert "breaking" in keywords
    assert "scientists" in keywords
    assert "nasa" in keywords
    assert "from" not in keywords  # Stopword


def test_jaccard_similarity_calculations():
    """Test Jaccard similarity index on overlapping tag sets."""
    set1 = {"#mars", "#space", "#nasa"}
    set2 = {"#mars", "#space", "#astronomy"}
    sim = compute_jaccard_similarity(set1, set2)
    assert sim == round(2.0 / 4.0, 4)  # 2 in common out of 4 union = 0.5


def test_hash_hamming_distance_and_similarity():
    """Test Hamming distance between exact, close, and distinct hashes."""
    hash1 = "a1b2c3d4e5f60718"
    hash2 = "a1b2c3d4e5f60718"  # Exact
    hash3 = "a1b2c3d4e5f60719"  # 1 bit difference
    hash4 = "ffffffffffffffff"  # High distance

    assert calculate_hash_hamming_distance(hash1, hash2) == 0
    assert calculate_hash_hamming_distance(hash1, hash3) == 1
    assert calculate_hash_hamming_distance(hash1, hash4) > 20

    assert hash_distance_to_similarity(0) == 1.0
    assert hash_distance_to_similarity(64) == 0.0


# ==============================================================================
# 2. FULL SIMILAR CONTENT ANALYZER TESTS
# ==============================================================================

@pytest.fixture
def test_analyzer():
    # Setup controlled repository
    repo = InMemoryContentRepository([
        HistoricalContentItem(
            item_id="hist_lockdown_hoax",
            text="Governments announce emergency lockdown protocols across all international airports!",
            hashtags=["#breaking", "#lockdown", "#emergency"],
            keywords=["governments", "emergency", "lockdown", "airports"],
            image_phash="f0e1d2c3b4a59687",
            first_seen_timestamp=datetime(2020, 3, 15, 8, 30, 0, tzinfo=timezone.utc),
            is_known_debunked_narrative=True,
            source_context="2020 airport lockdown hoax",
        ),
        HistoricalContentItem(
            item_id="hist_mars_mission",
            text="NASA rovers detect liquid water beneath Martian polar ice caps in deep radar soundings.",
            hashtags=["#space", "#mars", "#nasa"],
            keywords=["nasa", "rovers", "liquid", "water", "martian"],
            image_phash="a1b2c3d4e5f60718",
            first_seen_timestamp=datetime(2021, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
            is_known_debunked_narrative=False,
            source_context="Verified 2021 scientific announcement",
        ),
    ])
    return SimilarContentAnalyzer(repository=repo)


@pytest.mark.asyncio
async def test_fresh_original_content_high_score(test_analyzer: SimilarContentAnalyzer):
    """Test completely fresh, unrelated content receives a high similarity score (no recycled hoax match)."""
    text = "The local municipal council approved construction of a new public botanical garden and library."
    post_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    result = await test_analyzer.analyze(
        text=text,
        hashtags=["#LocalNews", "#Gardens"],
        post_timestamp=post_time,
    )

    assert result["similarity_score"] >= 80.0
    assert result["recycled_content"] is False
    assert result["text_similarity"] < 0.50
    assert "Content demonstrates high originality" in result["explanation"]


@pytest.mark.asyncio
async def test_recycled_viral_hoax_detection(test_analyzer: SimilarContentAnalyzer):
    """Test recycled 2020 hoax text recirculated in 2026 is flagged as recycled and penalized."""
    text = "Urgent: Governments announce emergency lockdown protocols across all airports due to a mystery virus!"
    post_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    result = await test_analyzer.analyze(
        text=text,
        hashtags=["#breaking", "#lockdown", "#emergency"],
        post_timestamp=post_time,
        image_phash_override="f0e1d2c3b4a59687",  # Matching image hash
    )

    assert result["recycled_content"] is True
    assert result["text_similarity"] > 0.80
    assert result["image_similarity"] == 1.0
    assert result["similarity_score"] < 40.0
    assert "RECYCLED_HISTORICAL_CONTENT_DETECTED" in result["flags"]
    assert "MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE" in result["flags"]
    assert "2020-03-15" in result["earliest_matching_timestamp"]


@pytest.mark.asyncio
async def test_empty_post_text_handling(test_analyzer: SimilarContentAnalyzer):
    """Test handling of empty post text."""
    result = await test_analyzer.analyze(text="")
    assert result["similarity_score"] == 75.0
    assert result["similar_content_count"] == 0
    assert "EMPTY_POST_TEXT" in result["flags"]


@pytest.mark.asyncio
async def test_image_comparison_graceful_fallback(test_analyzer: SimilarContentAnalyzer):
    """Test analyzer handles missing or invalid image URL gracefully without throwing exceptions."""
    text = "Astronomers observe distant galaxy redshift patterns."
    result = await test_analyzer.analyze(
        text=text,
        image_urls=["https://invalid-non-existent-domain-xyz-123.com/image.jpg"],
    )
    assert "similarity_score" in result
    assert result["image_similarity"] == 0.0
