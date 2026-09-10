"""Module 4: Similar Content & Hashtag Analysis Engine package."""

from app.modules.similar_content.analyzer import (
    SimilarContentAnalyzer,
    similar_content_analyzer,
)
from app.modules.similar_content.content_repository import (
    BaseContentRepository,
    HistoricalContentItem,
    InMemoryContentRepository,
    content_repository,
)
from app.modules.similar_content.hashtag_keyword import (
    compute_jaccard_similarity,
    extract_hashtags,
    extract_keywords,
)
from app.modules.similar_content.perceptual_hash import (
    calculate_hash_hamming_distance,
    compute_image_perceptual_hash,
    fetch_and_hash_image,
    hash_distance_to_similarity,
)

__all__ = [
    "BaseContentRepository",
    "HistoricalContentItem",
    "InMemoryContentRepository",
    "SimilarContentAnalyzer",
    "calculate_hash_hamming_distance",
    "compute_image_perceptual_hash",
    "compute_jaccard_similarity",
    "content_repository",
    "extract_hashtags",
    "extract_keywords",
    "fetch_and_hash_image",
    "hash_distance_to_similarity",
    "similar_content_analyzer",
]
