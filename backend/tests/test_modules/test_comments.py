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
from app.modules.comment_analysis.similarity import (
    compute_semantic_clusters,
    compute_semantic_similarity_features,
)
from app.modules.comment_analysis.temporal import compute_temporal_features
from app.schemas.domain_models import Comment


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def analyzer():
    return CommentAnalyzer(similarity_threshold=0.85, zscore_threshold=3.0)


# ==============================================================================
# 1. PREPROCESSING & EMOJI TESTS
# ==============================================================================

def test_extract_emojis_and_clean_text():
    """Test emoji extraction, embedding cleaning, and exact text normalization."""
    raw = "🔥 Check this out!! https://fake-news.com 🔥🔥"
    emojis = extract_emojis(raw)
    assert emojis == ["🔥", "🔥", "🔥"]

    cleaned_embed = clean_text_for_embedding(raw)
    assert "https://" not in cleaned_embed
    assert "🔥" in cleaned_embed

    exact_norm = normalize_text_for_exact_match(raw)
    assert exact_norm == "check this out"


def test_compute_emoji_features_diverse_vs_spam():
    """Test emoji Shannon entropy and distribution on diverse vs spam emojis."""
    diverse_comments = [
        "Great post! 👍",
        "Interesting findings 🤔",
        "Awesome research 🚀",
        "Looking forward to reading 📚",
    ]
    diverse_metrics = compute_emoji_features(diverse_comments)
    assert diverse_metrics["emoji_comment_ratio"] == 1.0
    assert diverse_metrics["emoji_entropy"] > 1.5
    assert diverse_metrics["unique_emojis"] >= 4
    assert diverse_metrics["excessive_emoji_ratio"] == 0.0

    spam_comments = [
        "🚨🚨🚨🚨🚨 BREAKING SCAM 🚨🚨🚨🚨🚨",
        "🚨🚨🚨🚨🚨 WATCH NOW 🚨🚨🚨🚨🚨",
    ]
    spam_metrics = compute_emoji_features(spam_comments)
    assert spam_metrics["excessive_emoji_ratio"] == 1.0
    assert spam_metrics["emoji_entropy"] == 0.0  # Only one distinct emoji used
    assert spam_metrics["unique_emojis"] == 1
    assert "🚨" in spam_metrics["emoji_distribution"]


# ==============================================================================
# 2. TEMPORAL & ANOMALY TESTS (Z-Score & IQR)
# ==============================================================================

def test_temporal_burst_detection_zscore_and_iqr():
    """Test burst detection when an inorganic spike of comments arrives in seconds."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    # 20 comments spread evenly (1 comment every 2 minutes for 40 minutes)
    organic_timestamps = [base_time + timedelta(minutes=i * 2) for i in range(20)]
    organic_temp = compute_temporal_features(organic_timestamps)
    assert organic_temp["zscore_burst_detected"] == 0.0
    assert organic_temp["iqr_burst_detected"] == 0.0
    assert organic_temp["temporal_anomaly_score"] == 0.0
    assert organic_temp["iqr_anomaly_info"]["outlier_count"] == 0

    # Inorganic spike: 20 comments within 10 seconds of each other
    spike_timestamps = [base_time + timedelta(seconds=i * 2) for i in range(20)]
    spike_temp = compute_temporal_features(spike_timestamps)
    assert spike_temp["zscore_burst_detected"] == 1.0
    assert spike_temp["z_score"] >= 3.0
    assert spike_temp["temporal_burst_score"] > 0.0
    assert spike_temp["iqr_anomaly_info"]["iqr_burst_detected"] is True


# ==============================================================================
# 3. SEMANTIC SIMILARITY & CLUSTERING TESTS
# ==============================================================================

def test_semantic_clustering_and_similarity():
    """Test Sentence-BERT semantic similarity and agglomerative clustering."""
    texts = [
        "Breaking: Space telescope confirms water vapor on habitable exoplanet.",
        "Breaking news: Astronomers verify atmospheric water vapor on nearby exoplanet.",
        "Water vapor detected on habitable exoplanet by space telescope team.",
        "What are you all having for dinner tonight?",
    ]
    clusters = compute_semantic_clusters(texts, similarity_threshold=0.75)
    assert clusters["num_clusters"] >= 2
    assert clusters["coordinated_cluster_count"] >= 1
    assert clusters["largest_cluster_size"] >= 3
    assert clusters["largest_cluster_ratio"] >= 0.75


# ==============================================================================
# 4. FULL MODULE 1 SUITE (8 SPECIFIED TEST CASES)
# ==============================================================================

# Case 1: Normal / Organic Comments
def test_normal_organic_comments(analyzer: CommentAnalyzer):
    """Test that diverse, organic comments yield a high credibility score (> 75)."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="I reviewed the research methodology and the sample size looks solid.", timestamp=base_time),
        Comment(text="Could you explain figure 3 in more detail regarding error margins?", timestamp=base_time + timedelta(minutes=5)),
        Comment(text="Great work team, waiting for the replication study results.", timestamp=base_time + timedelta(minutes=12)),
        Comment(text="Is there an open source repository for the simulation data?", timestamp=base_time + timedelta(minutes=25)),
    ]
    res = analyzer.analyze(comments)
    assert res["score"] >= 75.0
    assert res["status"] == "ORGANIC"
    assert res["comment_count"] == 4
    assert res["duplicate_ratio"] == 0.0
    assert res["debunk_ratio"] == 0.0
    assert res["cluster_information"]["num_clusters"] >= 2
    assert "HIGH_DUPLICATE_COMMENT_RATIO" not in res["detected_flags"]
    assert "COMMENTS_DEBUNK_CLAIM" not in res["detected_flags"]
    assert len(res["explanation"]) > 20


# Case 2: Duplicate Comments (Exact Copypasta)
def test_duplicate_comments(analyzer: CommentAnalyzer):
    """Test that exact copypasta comments are detected and duplicate_ratio is elevated."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="CLICK HERE FOR FREE CRYPTO AIRDROP $$$", timestamp=base_time),
        Comment(text="CLICK HERE FOR FREE CRYPTO AIRDROP $$$", timestamp=base_time + timedelta(seconds=5)),
        Comment(text="CLICK HERE FOR FREE CRYPTO AIRDROP $$$", timestamp=base_time + timedelta(seconds=10)),
        Comment(text="CLICK HERE FOR FREE CRYPTO AIRDROP $$$", timestamp=base_time + timedelta(seconds=15)),
    ]
    res = analyzer.analyze(comments)
    assert res["duplicate_ratio"] >= 0.75
    assert "HIGH_DUPLICATE_COMMENT_RATIO" in res["detected_flags"]
    assert res["status"] == "SPAM_DETECTED"
    # Adhere to rule: do not classify as fake solely because comments are spam
    assert res["score"] >= 40.0
    assert res["cluster_information"]["largest_cluster_size"] >= 3
    assert "duplicate ratio" in res["explanation"].lower()


# Case 3: Highly Similar Comments (Semantic Bot Farm)
def test_highly_similar_comments(analyzer: CommentAnalyzer):
    """Test that paraphrased bot farm comments are grouped into semantic clusters."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text="Invest now in crypto to earn huge daily profits with this link!", timestamp=base_time),
        Comment(text="Put your money in crypto today for massive daily returns at this link!", timestamp=base_time + timedelta(minutes=1)),
        Comment(text="Start crypto investing now and get huge daily earnings via this link!", timestamp=base_time + timedelta(minutes=2)),
        Comment(text="Join crypto investment today and receive huge daily returns through this link!", timestamp=base_time + timedelta(minutes=3)),
    ]
    res = analyzer.analyze(comments)
    assert res["semantic_similarity"] >= 0.70
    assert "SUSPICIOUS_SEMANTIC_COORDINATION" in res["detected_flags"]
    assert res["cluster_information"]["coordinated_cluster_count"] >= 1
    assert res["cluster_information"]["largest_cluster_ratio"] >= 0.50
    assert res["score"] < 80.0


# Case 4: Burst Comments (Temporal Spikes via Z-Score & IQR)
def test_burst_comments(analyzer: CommentAnalyzer):
    """Test that rapid arrival spikes trigger temporal burst score and Z-score/IQR flags."""
    base_time = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    comments = [
        Comment(text=f"Fast automated response number {i}", timestamp=base_time + timedelta(seconds=i))
        for i in range(15)
    ]
    res = analyzer.analyze(comments)
    assert res["temporal_burst_score"] > 0.0
    assert res["z_score"] >= 3.0
    assert res["iqr_anomaly_info"]["iqr_burst_detected"] is True
    assert "TEMPORAL_BURST_ACTIVITY_DETECTED" in res["detected_flags"]
    assert res["status"] in ["BURST_DETECTED", "SPAM_DETECTED"]


# Case 5: Skeptical / Debunking Comments
def test_skeptical_and_debunking_comments(analyzer: CommentAnalyzer):
    """Test that community debunking citing fact-checkers is detected and penalized."""
    comments = [
        Comment(text="This is completely fake news and already debunked by Snopes!"),
        Comment(text="Community notes needed: this video is a staged CGI hoax from 2019."),
        Comment(text="False information, please stop spreading this scam."),
        Comment(text="Interesting article though."),
    ]
    res = analyzer.analyze(comments)
    assert res["debunk_ratio"] >= 0.50
    assert res["status"] == "DEBUNKED"
    assert "COMMENTS_DEBUNK_CLAIM" in res["detected_flags"]
    assert "FACT_CHECK_CITED_IN_COMMENTS" in res["detected_flags"]
    assert res["score"] <= 40.0
    assert "debunking" in res["explanation"].lower()


# Case 6: Empty Comments
def test_empty_comments(analyzer: CommentAnalyzer):
    """Test that empty comment list returns neutral baseline without errors."""
    res = analyzer.analyze([])
    assert res["score"] == 50.0
    assert res["status"] == "NO_COMMENTS"
    assert res["comment_count"] == 0
    assert res["duplicate_ratio"] == 0.0
    assert res["semantic_similarity"] == 0.0
    assert res["temporal_burst_score"] == 0.0
    assert res["z_score"] == 0.0
    assert res["emoji_entropy"] == 0.0
    assert res["debunk_ratio"] == 0.0
    assert res["support_ratio"] == 0.0
    assert "NO_COMMENTS_AVAILABLE" in res["detected_flags"]
    assert res["cluster_information"]["num_clusters"] == 0


# Case 7: Single Comment
def test_single_comment(analyzer: CommentAnalyzer):
    """Test single comment evaluation without dividing by zero or erroring."""
    comment = Comment(text="This seems to be an interesting study on solar flare patterns.")
    res = analyzer.analyze([comment])
    assert res["comment_count"] == 1
    assert res["status"] == "SINGLE_COMMENT"
    assert res["duplicate_ratio"] == 0.0
    assert res["semantic_similarity"] == 0.0
    assert "SINGLE_COMMENT_ONLY" in res["detected_flags"]
    assert res["score"] >= 60.0


# Case 8: Malformed Comment Data
def test_malformed_comment_data(analyzer: CommentAnalyzer):
    """Test robustness against None items, missing text, non-string values, and dict payloads."""
    malformed_inputs = [
        None,
        {"text": None},
        {"text": "A valid comment passed as dict", "timestamp": "2026-09-10T10:00:00Z"},
        {"text": 12345},  # Integer text
        Comment(text="A valid Pydantic comment object"),
        {"text": "Another comment with invalid timestamp", "timestamp": "bad-date-format"},
        "",  # Empty string item
    ]
    res = analyzer.analyze(malformed_inputs)
    # Must not crash and should salvage valid items
    assert res["comment_count"] >= 3
    assert "MALFORMED_COMMENT_DATA" in res["detected_flags"]
    assert 0.0 <= res["score"] <= 100.0
    assert res["status"] is not None
    assert isinstance(res["cluster_information"], dict)
    assert isinstance(res["iqr_anomaly_info"], dict)
    assert isinstance(res["explanation"], str)
