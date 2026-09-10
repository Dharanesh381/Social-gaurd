"""Historical content repository and retrieval interface."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pydantic import BaseModel


class HistoricalContentItem(BaseModel):
    """Archived / known historical post record for provenance and similarity matching."""

    item_id: str
    text: str
    hashtags: list[str] = []
    keywords: list[str] = []
    image_phash: str | None = None
    first_seen_timestamp: datetime
    is_known_debunked_narrative: bool = False
    source_context: str = ""


class BaseContentRepository(ABC):
    """Abstract interface for retrieving related historical content."""

    @abstractmethod
    async def find_related_content(
        self,
        query_text: str,
        hashtags: list[str],
        image_phash: str | None = None,
        top_k: int = 5,
    ) -> list[HistoricalContentItem]:
        pass


class InMemoryContentRepository(BaseContentRepository):
    """In-memory historical corpus repository with baseline sample narratives."""

    def __init__(self, initial_items: list[HistoricalContentItem] | None = None):
        self._items: list[HistoricalContentItem] = initial_items or self._get_default_corpus()

    def add_item(self, item: HistoricalContentItem):
        self._items.append(item)

    async def find_related_content(
        self,
        query_text: str,
        hashtags: list[str],
        image_phash: str | None = None,
        top_k: int = 5,
    ) -> list[HistoricalContentItem]:
        # Returns all active repository records for similarity evaluation
        return self._items[:top_k]

    @staticmethod
    def _get_default_corpus() -> list[HistoricalContentItem]:
        """Default historical repository corpus representing known viral narratives and past events."""
        return [
            HistoricalContentItem(
                item_id="hist_001",
                text="NASA rovers detect liquid water beneath Martian polar ice caps in deep radar soundings.",
                hashtags=["#space", "#mars", "#nasa", "#science"],
                keywords=["nasa", "rovers", "liquid", "water", "martian", "polar", "radar"],
                image_phash="a1b2c3d4e5f60718",
                first_seen_timestamp=datetime(2021, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=False,
                source_context="Verified 2021 scientific radar research announcement",
            ),
            HistoricalContentItem(
                item_id="hist_002",
                text="BREAKING: Governments announce emergency lockdown protocols across all international airports due to mystery virus!",
                hashtags=["#breaking", "#lockdown", "#emergency", "#airport"],
                keywords=["governments", "emergency", "lockdown", "protocols", "international", "airports", "mystery", "virus"],
                image_phash="f0e1d2c3b4a59687",
                first_seen_timestamp=datetime(2020, 3, 15, 8, 30, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Debunked 2020 recycled viral hoax",
            ),
            HistoricalContentItem(
                item_id="hist_003",
                text="Free crypto airdrop giveaway! Send 0.1 ETH to verify your wallet and receive 2.0 ETH immediately.",
                hashtags=["#crypto", "#airdrop", "#giveaway", "#ethereum", "#free"],
                keywords=["free", "crypto", "airdrop", "giveaway", "wallet", "ethereum"],
                image_phash="1122334455667788",
                first_seen_timestamp=datetime(2022, 1, 10, 0, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Recycled cryptocurrency doubling scam template",
            ),
        ]


content_repository = InMemoryContentRepository()
