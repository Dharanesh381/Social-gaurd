"""Fact-Check In-Memory Caching Engine (Module 2).

Provides high-performance dual-tier in-memory caching for evidence verification:
1. Query-Level Cache: Stores raw Google Fact Check Tools API responses for claim queries.
   Prevents redundant external network HTTP requests, saves API quota, and avoids 429 rate limits.
2. Post-Level Cache: Stores complete Evidence Verification results for analyzed posts.
   When the exact same post or post URL is analyzed again, retrieves previous results instantly (< 1ms).

Features:
- Configurable TTL (default 24 hours).
- Bounded LRU eviction policy (max 1000 items) to prevent memory exhaustion.
- Thread-safe and asyncio-compatible via re-entrant locks.
- Real-time cache hit/miss statistics and cache clearing utilities.
"""

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import threading
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class FactCheckCache:
    """In-memory thread-safe LRU cache with TTL for Fact Check queries and post verification results."""

    def __init__(
        self,
        default_ttl_seconds: float | None = None,
        max_entries: int | None = None,
        enabled: bool | None = None,
    ):
        self.enabled = (
            enabled
            if enabled is not None
            else getattr(settings, "FACT_CHECK_CACHE_ENABLED", True)
        )
        self.default_ttl = (
            default_ttl_seconds
            if default_ttl_seconds is not None
            else float(getattr(settings, "FACT_CHECK_CACHE_TTL_SECONDS", 86400))
        )
        self.max_entries = (
            max_entries
            if max_entries is not None
            else int(getattr(settings, "FACT_CHECK_CACHE_MAX_ENTRIES", 1000))
        )

        self._query_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._post_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()

        # Metrics & telemetry
        self._query_hits = 0
        self._query_misses = 0
        self._post_hits = 0
        self._post_misses = 0

    @staticmethod
    def _normalize_query_key(query: str, language_code: str = "en") -> str:
        """Create a canonical normalized key for a claim search query."""
        cleaned = " ".join((query or "").strip().lower().split())
        lang = (language_code or "en").strip().lower()
        return f"{lang}:{cleaned}"

    @staticmethod
    def compute_post_fingerprint(
        post_text: str,
        image_urls: list[str] | None = None,
        post_id: str | None = None,
        post_url: str | None = None,
    ) -> str:
        """Compute deterministic SHA-256 fingerprint for a post.

        Combines:
        - post_id / post_url (if provided)
        - normalized post text (lowercased, whitespace collapsed)
        - sorted image URLs
        """
        clean_text = " ".join((post_text or "").strip().lower().split())
        clean_pid = (post_id or "").strip().lower()
        clean_purl = (post_url or "").strip().lower()

        clean_images = []
        if image_urls:
            clean_images = sorted(str(u).strip().lower() for u in image_urls if u)

        raw_payload = (
            f"pid:{clean_pid}|purl:{clean_purl}|txt:{clean_text}|imgs:{','.join(clean_images)}"
        )
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    # ==========================================================================
    # 1. QUERY-LEVEL CACHE (API Search Results)
    # ==========================================================================

    def get_query(
        self, query: str, language_code: str = "en"
    ) -> dict[str, Any] | None:
        """Retrieve cached Fact Check API response for a claim search query.

        Returns:
            Deep copy of cached dictionary with 'cached': True if found and valid, else None.
        """
        if not self.enabled or not query or not query.strip():
            return None

        key = self._normalize_query_key(query, language_code)
        now = datetime.now(timezone.utc)

        with self._lock:
            if key not in self._query_cache:
                self._query_misses += 1
                return None

            entry = self._query_cache[key]
            expires_at = entry.get("expires_at")
            if expires_at and now > expires_at:
                del self._query_cache[key]
                self._query_misses += 1
                return None

            # Mark as recently used in LRU order
            self._query_cache.move_to_end(key)
            self._query_hits += 1
            entry["hit_count"] = entry.get("hit_count", 0) + 1

            result = deepcopy(entry["data"])
            result["cached"] = True
            result["cached_at"] = entry["created_at"].isoformat()
            return result

    def set_query(
        self,
        query: str,
        result: dict[str, Any],
        language_code: str = "en",
        ttl_seconds: float | None = None,
    ) -> None:
        """Store Google Fact Check Tools API response in query cache."""
        if not self.enabled or not query or not query.strip():
            return

        # Do not cache transient connection/rate limit errors
        status = result.get("status")
        if status in ("RATE_LIMITED", "TIMEOUT", "CONNECTION_ERROR", "API_ERROR"):
            return

        key = self._normalize_query_key(query, language_code)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None

        with self._lock:
            if key in self._query_cache:
                self._query_cache.move_to_end(key)

            self._query_cache[key] = {
                "data": deepcopy(result),
                "created_at": now,
                "expires_at": expires_at,
                "hit_count": 0,
            }

            # Enforce LRU size limit
            while len(self._query_cache) > self.max_entries:
                self._query_cache.popitem(last=False)

    # ==========================================================================
    # 2. POST-LEVEL CACHE (Evidence Verification Results)
    # ==========================================================================

    def get_post(
        self,
        post_text: str,
        image_urls: list[str] | None = None,
        post_id: str | None = None,
        post_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve previously computed Module 2 Evidence Verification result for a post.

        Returns:
            Deep copy of cached result with 'from_cache': True if found and valid, else None.
        """
        if not self.enabled:
            return None

        # Require at least post_text, post_id, or post_url
        if not (post_text and post_text.strip()) and not post_id and not post_url:
            return None

        fingerprint = self.compute_post_fingerprint(
            post_text=post_text,
            image_urls=image_urls,
            post_id=post_id,
            post_url=post_url,
        )
        now = datetime.now(timezone.utc)

        with self._lock:
            if fingerprint not in self._post_cache:
                self._post_misses += 1
                return None

            entry = self._post_cache[fingerprint]
            expires_at = entry.get("expires_at")
            if expires_at and now > expires_at:
                del self._post_cache[fingerprint]
                self._post_misses += 1
                return None

            # Mark recently used in LRU
            self._post_cache.move_to_end(fingerprint)
            self._post_hits += 1
            entry["hit_count"] = entry.get("hit_count", 0) + 1

            result = deepcopy(entry["data"])
            result["from_cache"] = True
            result["cached"] = True
            result["cached_at"] = entry["created_at"].isoformat()

            flags = list(result.get("flags", []))
            if "FACT_CHECK_CACHE_HIT" not in flags:
                flags.append("FACT_CHECK_CACHE_HIT")
            result["flags"] = flags

            return result

    def set_post(
        self,
        post_text: str,
        result: dict[str, Any],
        image_urls: list[str] | None = None,
        post_id: str | None = None,
        post_url: str | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """Store complete Module 2 Evidence Verification result for a post."""
        if not self.enabled:
            return

        if not (post_text and post_text.strip()) and not post_id and not post_url:
            return

        # Do not cache failed unconfigured states
        status = result.get("status")
        if status in ("API_KEY_MISSING", "ERROR"):
            return

        fingerprint = self.compute_post_fingerprint(
            post_text=post_text,
            image_urls=image_urls,
            post_id=post_id,
            post_url=post_url,
        )
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None

        with self._lock:
            if fingerprint in self._post_cache:
                self._post_cache.move_to_end(fingerprint)

            self._post_cache[fingerprint] = {
                "data": deepcopy(result),
                "created_at": now,
                "expires_at": expires_at,
                "hit_count": 0,
            }

            while len(self._post_cache) > self.max_entries:
                self._post_cache.popitem(last=False)

    # ==========================================================================
    # 3. UTILITIES & TELEMETRY
    # ==========================================================================

    def clear(self) -> None:
        """Reset both query and post-level caches and hit counters."""
        with self._lock:
            self._query_cache.clear()
            self._post_cache.clear()
            self._query_hits = 0
            self._query_misses = 0
            self._post_hits = 0
            self._post_misses = 0

    def stats(self) -> dict[str, Any]:
        """Return operational cache telemetry metrics."""
        with self._lock:
            total_requests = self._query_hits + self._query_misses + self._post_hits + self._post_misses
            total_hits = self._query_hits + self._post_hits
            hit_ratio = round((total_hits / total_requests), 4) if total_requests > 0 else 0.0

            return {
                "enabled": self.enabled,
                "default_ttl_seconds": self.default_ttl,
                "max_entries": self.max_entries,
                "query_cache_size": len(self._query_cache),
                "post_cache_size": len(self._post_cache),
                "query_hits": self._query_hits,
                "query_misses": self._query_misses,
                "post_hits": self._post_hits,
                "post_misses": self._post_misses,
                "total_hits": total_hits,
                "total_requests": total_requests,
                "hit_ratio": hit_ratio,
            }


# Global singleton instance
fact_check_cache = FactCheckCache()

