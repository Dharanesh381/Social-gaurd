"""Platform extraction abstractions and interfaces.

Keeps scraping / DOM parsing decoupled from the AI and backend analysis engines.
"""

from abc import ABC, abstractmethod

from app.schemas.domain_models import SocialMediaPost


class BasePlatformExtractor(ABC):
    """Abstract base class for platform-specific DOM and structured data extractors."""

    @abstractmethod
    def extract_post_from_html(self, html_content: str, source_url: str | None = None) -> SocialMediaPost:
        """Parse raw HTML / DOM string into a standard SocialMediaPost entity."""
