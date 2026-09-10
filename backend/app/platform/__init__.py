"""
Platform Extraction Package
Provides modular, platform-specific content extractors that parse publicly visible DOM / HTML.
"""

from app.platform.base import BasePlatformExtractor
from app.platform.reddit_extractor import RedditExtractor, reddit_extractor

__all__ = ["BasePlatformExtractor", "RedditExtractor", "reddit_extractor"]
