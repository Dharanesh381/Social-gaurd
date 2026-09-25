"""Google Fact Check Tools API asynchronous client (Phase 4)."""

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleFactCheckClient:
    """Client for querying the Google Fact Check Tools API (ClaimSearch endpoint).

    API Reference:
    https://toolbox.google.com/factcheck/apis
    https://factchecktools.googleapis.com/v1alpha1/claims:search
    """

    BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def __init__(self, api_key: str | None = None, timeout: float = 6.0):
        # Read API key strictly from settings/environment, never hardcoded
        self.api_key = api_key if api_key is not None else getattr(settings, "GOOGLE_FACT_CHECK_API_KEY", "")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._client_loop = None

    def _get_client(self) -> httpx.AsyncClient:
        """Retrieve or initialize persistent AsyncClient with connection pooling bound to current loop."""
        import asyncio
        try:
            curr_loop = asyncio.get_running_loop()
        except RuntimeError:
            curr_loop = None

        if self._client is None or self._client.is_closed or self._client_loop != curr_loop:
            timeout_config = httpx.Timeout(self.timeout, connect=3.0, read=self.timeout)
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            self._client = httpx.AsyncClient(timeout=timeout_config, limits=limits)
            self._client_loop = curr_loop
        return self._client

    async def aclose(self) -> None:
        """Close persistent HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def search_claims(
        self, query: str, language_code: str = "en", max_results: int = 5
    ) -> dict[str, Any]:
        """Search Google Fact Check Tools for matching claim reviews.

        Returns:
            Raw API JSON dictionary or standardized error response dict.
        """
        if not self.api_key:
            logger.warning("Google Fact Check API Key is missing. Skipping external search.")
            return {"claims": [], "status": "API_KEY_MISSING"}

        if not query or not query.strip():
            return {"claims": [], "status": "EMPTY_QUERY"}

        params = {
            "query": query.strip(),
            "languageCode": language_code,
            "pageSize": max_results,
            "key": self.api_key,
        }

        try:
            client = self._get_client()
            response = await client.get(self.BASE_URL, params=params)

            if response.status_code == 200:
                try:
                    data = response.json()
                except (ValueError, json.JSONDecodeError):
                    logger.error("Failed to parse JSON response from Google Fact Check API")
                    return {
                        "claims": [],
                        "status": "MALFORMED_RESPONSE",
                        "error": "Invalid JSON response from server",
                    }

                claims = data.get("claims", [])
                logger.info("Fact check API query '%s' returned %d claims", query[:30], len(claims))
                return {"claims": claims, "status": "SUCCESS"}

            elif response.status_code == 429:
                logger.warning("Google Fact Check API rate limit reached (429).")
                return {"claims": [], "status": "RATE_LIMITED", "error": "Rate limit exceeded"}

            elif response.status_code == 400:
                logger.warning("Google Fact Check API Bad Request (400)")
                return {"claims": [], "status": "BAD_REQUEST", "error": "Bad request sent to API"}

            else:
                logger.error("Google Fact Check API error (%d)", response.status_code)
                return {
                    "claims": [],
                    "status": "API_ERROR",
                    "error": f"HTTP status {response.status_code}",
                }

        except httpx.TimeoutException:
            logger.warning("Google Fact Check API request timed out for query: %s", query[:30])
            return {"claims": [], "status": "TIMEOUT", "error": "Request timed out"}

        except (httpx.ConnectError, httpx.NetworkError):
            logger.error("Connection error to Google Fact Check API: host unreachable")
            return {"claims": [], "status": "CONNECTION_ERROR", "error": "Connection to API failed"}

        except Exception as exc:
            logger.error("Connection error to Google Fact Check API: %s", exc.__class__.__name__)
            return {"claims": [], "status": "CONNECTION_ERROR", "error": "Connection to API failed"}


fact_check_client = GoogleFactCheckClient()
