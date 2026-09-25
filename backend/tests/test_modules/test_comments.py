"""Unit tests for Module 1: Comment Analysis Engine."""

from datetime import datetime, timedelta, timezone
import pytest

from app.modules.comment_analysis.analyzer import CommentAnalyzer
from app.modules.comment_analysis.preprocessing import (
    clean_text_for_embedding,
    compute_emoji_features,
    extract_emojis,
    normalize_text_for_exact_match,
)
from app.modules.comment_analysis.temporal import compute_temporal_features
from app.schemas.domain_models import Comment


# ==============================================================================
# 1. PREPROCESSING & EMOJI TESTS
# ==============================================================================

def test_extract_emojis_and_clean_text():
    """Test emoji extraction and text normalization."""
    raw = "🔥 Check this out!! https://fake-news.com 🔥🔥"
    emojis = extract_emojis(raw)
    assert emojis == ["🔥", "🔥", "🔥"]

    cleaned_embed = clean_text_for_embedding(raw)
    assert "https://" not in cleaned_embed
    assert "🔥" in cleaned_embed

    exact_norm = normalize_text_for_exact_match(raw)
    assert exact_norm == "check this out"


def test_compute_emoji_features_diverse_vs_spam():
    """Test emoji entropy on diverse emojis vs repetitive spam."""
    diverse_comments = [
        "Great post! 👍",
        "Interesting findings 🤔",
        "Awesome research 🚀",
        "Looking forward to reading 📚",
    ]
    diverse_metrics = compute_emoji_features(diverse_comments)
    assert diverse_metrics["emoji_comment_ratio"] == 1.0
    assert diverse_metrics["emoji_entropy"] > 1.5
    assert diverse_metrics["excessive_emoji_ratio"] == 0.0

    spam_comments = [
        "🚨🚨🚨🚨🚨 BREAKING SCAM 🚨🚨🚨🚨🚨",
        "🚨🚨🚨🚨🚨 WATCH NOW 🚨🚨🚨🚨🚨",
    ]
    spam_metrics = compute_emoji_features(spam_comments)
    assert spam_metrics["excessive_emoji_ratio"] == 1.0
    assert spam_metrics["emoji_entropy"] == 0.0  # Only one distinct emoji used


# ==============================================================================
# 2. TEMPORAL & ANOMALY TESTS
# ==============================================================================

def test_temporal_burst_detection_zscore_and_iqr():
    """Test burst detection when an inorganic spike of comments arrives in one minute."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    
    # 20 comments spread evenly (1 comment every 2 minutes for 40 minutes)
    organic_timestamps = [base_time + timedelta(minutes=i * 2) for i in range(20)]
    organic_temp = compute_temporal_features(organic_timestamps)
    assert organic_temp["zscore_burst_detected"] == 0.0
    assert organic_temp["iqr_burst_detected"] == 0.0
    assert organic_temp["temporal_anomaly_score"] == 0.0

    # Inorganic spike: 20 comments within 10 seconds of each other
    spike_timestamps = [base_time + timedelta(seconds=i * 2) for i in range(20)]
    spike_temp = compute_temporal_features(spike_timestamps)
    assert spike_temp["zscore_burst_detected"] == 1.0
    assert spike_temp["temporal_anomaly_score"] > 0.0


# ==============================================================================
# 3. FULL COMMENT ANALYZER & EDGE CASES TESTS
# ==============================================================================

@pytest.fixture
def analyzer():
    return CommentAnalyzer(similarity_threshold=0.85, zscore_threshold=3.0)


def test_empty_comments_handling(analyzer: CommentAnalyzer):
    """Test analyzer handles empty comment lists gracefully."""
    result = analyzer.analyze([])
    assert result["comment_score"] == 50.0  # Neutral baseline
    assert result["metrics"]["comment_count"] == 0
    assert "NO_COMMENTS_AVAILABLE" in result["flags"]


def test_single_comment_handling(analyzer: CommentAnalyzer):
    """Test analyzer handles a single comment without crashing."""
    comment = Comment(text="This is an interesting perspective on climate models.")
    result = analyzer.analyze([comment])
    assert result["comment_score"] == 65.0
    assert result["metrics"]["comment_count"] == 1
    assert "SINGLE_COMMENT_ONLY" in result["flags"]


def test_organic_diverse_comments_high_score(analyzer: CommentAnalyzer):
    """Test that diverse, unique organic comments yield a high score (> 80)."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="I reviewed the research methodology and the sample size looks solid.", timestamp=base_time),
        Comment(text="Could you explain figure 3 in more detail regarding error margins?", timestamp=base_time + timedelta(minutes=5)),
        Comment(text="Great work team, waiting for the replication study results.", timestamp=base_time + timedelta(minutes=12)),
        Comment(text="Is there an open source repository for the simulation data?", timestamp=base_time + timedelta(minutes=25)),
    ]
    result = analyzer.analyze(comments)
    assert result["comment_score"] >= 80.0
    assert result["metrics"]["duplicate_ratio"] == 0.0
    assert len(result["flags"]) == 0


def test_exact_repeated_copypasta_spam(analyzer: CommentAnalyzer):
    """Test that identical duplicate spam is flagged and penalizes score heavily."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time),
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time + timedelta(seconds=5)),
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time + timedelta(seconds=10)),
        Comment(text="CLICK HERE FOR FREE BITCOIN AIRDROP $$$", timestamp=base_time + timedelta(seconds=15)),
    ]
    result = analyzer.analyze(comments)
    assert result["comment_score"] < 60.0
    assert result["metrics"]["duplicate_ratio"] >= 0.75
    assert "HIGH_DUPLICATE_COMMENT_RATIO" in result["flags"]


def test_near_duplicate_semantic_bot_farm(analyzer: CommentAnalyzer):
    """Test that semantically paraphrased bot comments are detected by S-BERT."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="Invest now in crypto to earn huge daily profits with this link!", timestamp=base_time),
        Comment(text="Put your money in crypto today for massive daily returns at this link!", timestamp=base_time + timedelta(minutes=1)),
        Comment(text="Start crypto investing now and get huge daily earnings via this link!", timestamp=base_time + timedelta(minutes=2)),
        Comment(text="Join crypto investment today and receive huge daily returns through this link!", timestamp=base_time + timedelta(minutes=3)),
    ]
    result = analyzer.analyze(comments)
    assert result["metrics"]["average_similarity"] > 0.75
    assert "SUSPICIOUS_SEMANTIC_COORDINATION" in result["flags"]
    assert result["comment_score"] < 75.0


def test_comment_fact_check_community_debunk(analyzer: CommentAnalyzer):
    """Test that comments debunking a claim are detected and penalize the comment score."""
    comments = [
        Comment(text="This is completely fake news and already debunked by Snopes!"),
        Comment(text="Community notes needed: this video is a staged CGI hoax from 2019."),
        Comment(text="False information, please stop spreading this scam."),
        Comment(text="Interesting article though."),
    ]
    result = analyzer.analyze(comments)
    assert result["fact_check"]["verdict"] == "DEBUNKED_BY_COMMUNITY"
    assert result["fact_check"]["debunk_ratio"] >= 0.50
    assert result["fact_check"]["has_fact_checker_reference"] is True
    assert "COMMENTS_DEBUNK_CLAIM" in result["flags"]
    assert "FACT_CHECK_CITED_IN_COMMENTS" in result["flags"]
    assert result["comment_score"] <= 35.0


def test_comment_fact_check_community_support(analyzer: CommentAnalyzer):
    """Test that comments confirming and verifying a claim are detected and rewarded."""
    comments = [
        Comment(text="This was verified and confirmed by Reuters today."),
        Comment(text="Legit and accurate reporting from official sources."),
        Comment(text="I checked the primary research paper, this is true."),
    ]
    result = analyzer.analyze(comments)
    assert result["fact_check"]["verdict"] == "SUPPORTED_BY_COMMENTS"
    assert result["fact_check"]["support_ratio"] >= 0.60
    assert "COMMENTS_VERIFY_CLAIM" in result["flags"]
    assert result["comment_score"] >= 80.0

