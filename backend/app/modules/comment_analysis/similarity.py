"""Sentence-BERT embedding generation and semantic similarity computation."""

import logging
import threading
from collections import OrderedDict
from typing import Any

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


def compute_semantic_clusters(
    cleaned_texts: list[str],
    similarity_threshold: float = 0.80,
    custom_model=None,
) -> dict[str, Any]:
    """Group comments into semantic clusters using Sentence-BERT embeddings.

    Uses Agglomerative Clustering on pairwise cosine distance matrix.
    Comments with cosine similarity >= similarity_threshold are grouped into cohesive clusters.

    Returns:
        Dict containing:
        - num_clusters: Total distinct clusters identified
        - total_clusters: Alias for num_clusters
        - coordinated_cluster_count: Number of clusters containing >= 2 comments (bot farm / copypasta clusters)
        - largest_cluster_size: Maximum comments in a single cluster
        - largest_cluster_ratio: Proportion of comments belonging to the largest cluster
        - clusters: List of cluster objects with cluster_id, size, sample_text, comment_indices, cohesion
    """
    n = len(cleaned_texts)
    if n == 0:
        return {
            "num_clusters": 0,
            "total_clusters": 0,
            "coordinated_cluster_count": 0,
            "largest_cluster_size": 0,
            "largest_cluster_ratio": 0.0,
            "clusters": [],
        }

    if n == 1:
        return {
            "num_clusters": 1,
            "total_clusters": 1,
            "coordinated_cluster_count": 0,
            "largest_cluster_size": 1,
            "largest_cluster_ratio": 1.0,
            "clusters": [
                {
                    "cluster_id": 0,
                    "size": 1,
                    "sample_text": cleaned_texts[0][:150],
                    "comment_indices": [0],
                    "cohesion": 1.0,
                }
            ],
        }

    model = custom_model or get_sbert_model()
    embeddings = get_cached_embeddings(cleaned_texts, model=model)
    sim_matrix = cosine_similarity(embeddings)
    dist_matrix = np.clip(1.0 - sim_matrix, 0.0, 2.0)

    dist_threshold = max(0.01, 1.0 - similarity_threshold)

    try:
        from sklearn.cluster import AgglomerativeClustering

        clustering = AgglomerativeClustering(
            metric="precomputed",
            linkage="average",
            distance_threshold=dist_threshold,
            n_clusters=None,
        )
        labels = clustering.fit_predict(dist_matrix)
    except Exception as exc:
        logger.warning("Clustering fallback due to error: %s", exc)
        # Fallback: connected components on adjacency matrix (sim >= similarity_threshold)
        adj = (sim_matrix >= similarity_threshold).astype(int)
        visited = set()
        labels = np.zeros(n, dtype=int)
        cur_label = 0
        for i in range(n):
            if i not in visited:
                queue = [i]
                visited.add(i)
                while queue:
                    node = queue.pop(0)
                    labels[node] = cur_label
                    for neighbor in np.where(adj[node])[0]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                cur_label += 1

    # Aggregate clusters
    cluster_groups: dict[int, list[int]] = {}
    for idx, lbl in enumerate(labels):
        cluster_groups.setdefault(int(lbl), []).append(idx)

    cluster_list = []
    for c_id, indices in cluster_groups.items():
        size = len(indices)
        if size > 1:
            sub_sims = sim_matrix[np.ix_(indices, indices)]
            triu_sub = sub_sims[np.triu_indices(size, k=1)]
            cohesion = float(np.mean(triu_sub)) if len(triu_sub) > 0 else 1.0
        else:
            cohesion = 1.0

        cluster_list.append({
            "cluster_id": c_id,
            "size": size,
            "sample_text": cleaned_texts[indices[0]][:150],
            "comment_indices": indices,
            "cohesion": round(cohesion, 4),
        })

    # Sort clusters by size descending
    cluster_list.sort(key=lambda x: x["size"], reverse=True)
    coordinated_count = sum(1 for c in cluster_list if c["size"] >= 2)
    largest_size = cluster_list[0]["size"] if cluster_list else 0
    largest_ratio = round(largest_size / n, 4) if n > 0 else 0.0

    return {
        "num_clusters": len(cluster_list),
        "total_clusters": len(cluster_list),
        "coordinated_cluster_count": coordinated_count,
        "largest_cluster_size": largest_size,
        "largest_cluster_ratio": largest_ratio,
        "clusters": cluster_list,
    }
