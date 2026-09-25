"""Sentence-BERT embedding generation and semantic similarity computation."""

import logging
import threading
from collections import OrderedDict

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings

logger = logging.getLogger(__name__)

# Global model cache and thread lock to avoid duplicate instances
_SBERT_LOCK = threading.Lock()
_SBERT_MODEL = None

# Bounded LRU cache for text embeddings (max 1000 items, ~1.5MB total RAM)
_EMBEDDING_CACHE: OrderedDict[str, np.ndarray] = OrderedDict()
_MAX_EMBEDDING_CACHE_SIZE = 1000


def get_sbert_model():
    """Retrieve or lazy-load the Sentence-BERT model singleton with thread-safety."""
    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        with _SBERT_LOCK:
            if _SBERT_MODEL is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    model_name = getattr(settings, "SBERT_MODEL_NAME", "all-MiniLM-L6-v2")
                    device = getattr(settings, "DEVICE", "cpu")
                    logger.info("Loading Sentence-BERT model '%s' on %s...", model_name, device)
                    _SBERT_MODEL = SentenceTransformer(model_name, device=device)
                except Exception as exc:
                    logger.error("Failed to load Sentence-BERT model: %s", exc)
                    raise exc
    return _SBERT_MODEL


def get_cached_embeddings(texts: list[str], model=None) -> np.ndarray:
    """Encode texts using SentenceTransformer with thread-safe LRU caching for repeated analysis."""
    if not texts:
        return np.empty((0, 384))

    active_model = model or get_sbert_model()
    embeddings_with_idx = []
    missing_indices = []
    missing_texts = []

    for idx, text in enumerate(texts):
        clean_key = str(text).strip()
        with _SBERT_LOCK:
            if clean_key in _EMBEDDING_CACHE:
                _EMBEDDING_CACHE.move_to_end(clean_key)
                embeddings_with_idx.append((idx, _EMBEDDING_CACHE[clean_key]))
                continue

        missing_indices.append(idx)
        missing_texts.append(text)

    if missing_texts:
        new_embeddings = active_model.encode(missing_texts, convert_to_numpy=True, show_progress_bar=False)
        with _SBERT_LOCK:
            for orig_idx, key_text, emb in zip(missing_indices, missing_texts, new_embeddings):
                clean_key = str(key_text).strip()
                if len(_EMBEDDING_CACHE) >= _MAX_EMBEDDING_CACHE_SIZE:
                    _EMBEDDING_CACHE.popitem(last=False)
                _EMBEDDING_CACHE[clean_key] = emb
                embeddings_with_idx.append((orig_idx, emb))

    # Reconstruct array matching original input sequence
    embeddings_with_idx.sort(key=lambda x: x[0])
    return np.array([e[1] for e in embeddings_with_idx])


def compute_semantic_similarity_features(
    cleaned_texts: list[str],
    similarity_threshold: float = 0.85,
    custom_model=None,
) -> dict[str, float]:
    """Compute pairwise cosine similarities and near-duplicate metrics using Sentence-BERT.

    Args:
        cleaned_texts: Preprocessed non-empty comment texts.
        similarity_threshold: Cosine similarity cutoff for near-duplicates (default 0.85).
        custom_model: Optional SentenceTransformer model injection for testing.

    Returns:
        Dict containing:
        - average_similarity: Mean upper-triangular pairwise cosine similarity (0.0 to 1.0)
        - max_similarity: Maximum pairwise similarity observed
        - near_duplicate_ratio: Proportion of pairs exceeding similarity_threshold
        - near_duplicate_comment_ratio: Proportion of comments involved in at least one near-duplicate pair
    """
    n = len(cleaned_texts)
    if n < 2:
        return {
            "average_similarity": 0.0,
            "max_similarity": 0.0,
            "near_duplicate_ratio": 0.0,
            "near_duplicate_comment_ratio": 0.0,
        }

    model = custom_model or get_sbert_model()
    embeddings = get_cached_embeddings(cleaned_texts, model=model)

    # Compute pairwise cosine similarity matrix
    sim_matrix = cosine_similarity(embeddings)

    # Extract upper triangular indices (excluding diagonal)
    triu_indices = np.triu_indices(n, k=1)
    pair_similarities = sim_matrix[triu_indices]

    if len(pair_similarities) == 0:
        return {
            "average_similarity": 0.0,
            "max_similarity": 0.0,
            "near_duplicate_ratio": 0.0,
            "near_duplicate_comment_ratio": 0.0,
        }

    avg_sim = float(np.mean(pair_similarities))
    max_sim = float(np.max(pair_similarities))

    # Near duplicate pair ratio
    near_dup_pairs = np.sum(pair_similarities >= similarity_threshold)
    near_dup_ratio = float(near_dup_pairs / len(pair_similarities))

    # Identify individual comments involved in near duplicates
    near_dup_comments_set = set()
    rows, cols = triu_indices
    for i, j, sim in zip(rows, cols, pair_similarities):
        if sim >= similarity_threshold:
            near_dup_comments_set.add(int(i))
            near_dup_comments_set.add(int(j))

    near_dup_comment_ratio = float(len(near_dup_comments_set) / n)

    return {
        "average_similarity": round(max(0.0, min(1.0, avg_sim)), 4),
        "max_similarity": round(max(0.0, min(1.0, max_sim)), 4),
        "near_duplicate_ratio": round(near_dup_ratio, 4),
        "near_duplicate_comment_ratio": round(near_dup_comment_ratio, 4),
    }
