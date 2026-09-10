"""Module 1: Comment Analysis Engine package."""

from app.modules.comment_analysis.analyzer import (
    CommentAnalyzer,
    comment_analyzer,
)
from app.modules.comment_analysis.preprocessing import (
    clean_text_for_embedding,
    compute_emoji_features,
    extract_emojis,
    normalize_text_for_exact_match,
)
from app.modules.comment_analysis.similarity import (
    compute_semantic_similarity_features,
    get_sbert_model,
)
from app.modules.comment_analysis.temporal import (
    compute_temporal_features,
)

__all__ = [
    "CommentAnalyzer",
    "clean_text_for_embedding",
    "comment_analyzer",
    "compute_emoji_features",
    "compute_semantic_similarity_features",
    "compute_temporal_features",
    "extract_emojis",
    "get_sbert_model",
    "normalize_text_for_exact_match",
]
