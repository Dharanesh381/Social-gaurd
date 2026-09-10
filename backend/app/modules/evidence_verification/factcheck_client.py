"""Google Fact Check Tools API asynchronous client."""

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

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        # Read API key strictly from settings/environment, never hardcoded
        self.api_key = api_key or getattr(settings, "GOOGLE_FACT_CHECK_API_KEY", "")
        self.timeout = timeout

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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.BASE_URL, params=params)

                if response.status_code == 200:
                    data = response.json()
                    claims = data.get("claims", [])
                    logger.info("Fact check API query '%s' returned %d claims", query[:30], len(claims))
                    return {"claims": claims, "status": "SUCCESS"}

                elif response.status_code == 429:
                    logger.warning("Google Fact Check API rate limit reached (429).")
                    return {"claims": [], "status": "RATE_LIMITED", "error": "Rate limit exceeded"}

                elif response.status_code == 400:
                    logger.warning("Google Fact Check API Bad Request (400): %s", response.text)
                    return {"claims": [], "status": "BAD_REQUEST", "error": response.text}

                else:
                    logger.error("Google Fact Check API error (%d): %s", response.status_code, response.text)
                    return {
                        "claims": [],
                        "status": "API_ERROR",
                        "error": f"HTTP status {response.status_code}",
                    }

        except httpx.TimeoutException:
            logger.warning("Google Fact Check API request timed out for query: %s", query[:30])
            return {"claims": [], "status": "TIMEOUT", "error": "Request timed out"}

        except Exception as exc:
            logger.error("Unexpected error connecting to Google Fact Check API: %s", exc)
            return {"claims": [], "status": "CONNECTION_ERROR", "error": str(exc)}


fact_check_client = GoogleFactCheckClient()
