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
    image_dhash: str | None = None
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
        image_dhash: str | None = None,
        top_k: int = 5,
    ) -> list[HistoricalContentItem]:
        pass


class InMemoryContentRepository(BaseContentRepository):
    """In-memory historical corpus repository with baseline sample narratives."""

    def __init__(self, initial_items: list[HistoricalContentItem] | None = None):
        self._items: list[HistoricalContentItem] = initial_items or self._get_default_corpus()

    def add_item(self, item: HistoricalContentItem):
        """Add a verified item to the corpus, avoiding exact duplicates."""
        if any(x.item_id == item.item_id or x.text.strip().lower() == item.text.strip().lower() for x in self._items):
            return
        self._items.append(item)
        # Cap corpus to 200 items in memory
        if len(self._items) > 200:
            self._items.pop(0)

    def reset(self):
        """Reset repository back to default canonical corpus."""
        self._items = self._get_default_corpus()

    async def find_related_content(
        self,
        query_text: str,
        hashtags: list[str],
        image_phash: str | None = None,
        image_dhash: str | None = None,
        top_k: int = 50,
    ) -> list[HistoricalContentItem]:
        """Returns active repository records for similarity evaluation.

        For in-memory corpus (<= 150 items), returns all candidates to guarantee zero false-negatives.
        """
        if len(self._items) <= 150:
            return list(self._items)
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
                image_dhash="1a2b3c4d5e6f7081",
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
                image_dhash="0f1e2d3c4b5a6978",
                first_seen_timestamp=datetime(2020, 3, 15, 8, 30, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Debunked 2020 recycled viral airport lockdown hoax",
            ),
            HistoricalContentItem(
                item_id="hist_003",
                text="Free crypto airdrop giveaway! Send 0.1 ETH to verify your wallet and receive 2.0 ETH immediately.",
                hashtags=["#crypto", "#airdrop", "#giveaway", "#ethereum", "#free"],
                keywords=["free", "crypto", "airdrop", "giveaway", "wallet", "ethereum"],
                image_phash="1122334455667788",
                image_dhash="8877665544332211",
                first_seen_timestamp=datetime(2022, 1, 10, 0, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Recycled cryptocurrency doubling scam template",
            ),
            HistoricalContentItem(
                item_id="hist_004",
                text="BREAKING: Emergency nationwide lockdown declared tonight across all major international airports due to unknown airborne pathogen outbreak! Stock up immediately!",
                hashtags=["#breakingnews", "#lockdown", "#emergency"],
                keywords=["emergency", "nationwide", "lockdown", "airports", "pathogen", "outbreak", "stock"],
                image_phash="f0e1d2c3b4a59687",
                image_dhash="0f1e2d3c4b5a6978",
                first_seen_timestamp=datetime(2020, 3, 16, 9, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Debunked 2020 viral airport pathogen rumor",
            ),
            HistoricalContentItem(
                item_id="hist_005",
                text="UNESCO has officially declared our National Anthem as the best national anthem in the world! Share with everyone to spread pride.",
                hashtags=["#unesco", "#pride", "#anthem", "#viral"],
                keywords=["unesco", "declared", "national", "anthem", "best", "world"],
                image_phash="33445566778899aa",
                image_dhash="aa99887766554433",
                first_seen_timestamp=datetime(2014, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Debunked recurring UNESCO viral forward hoax",
            ),
            HistoricalContentItem(
                item_id="hist_006",
                text="NASA confirms 15 days of total darkness will engulf Earth starting next month due to rare planetary alignment between Venus and Jupiter.",
                hashtags=["#nasa", "#space", "#darkness", "#alert"],
                keywords=["nasa", "confirms", "darkness", "engulf", "earth", "planetary", "alignment", "venus", "jupiter"],
                image_phash="5566778899aabbcc",
                image_dhash="ccbbaa9988776655",
                first_seen_timestamp=datetime(2015, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Debunked recurring NASA 15 days of darkness viral hoax",
            ),
            HistoricalContentItem(
                item_id="hist_007",
                text="WhatsApp will begin charging monthly fees tomorrow unless you forward this message to 10 contacts to confirm your active status.",
                hashtags=["#whatsapp", "#fees", "#forward", "#viral"],
                keywords=["whatsapp", "charging", "monthly", "fees", "forward", "message", "contacts", "active"],
                image_phash="778899aabbccddee",
                image_dhash="eeddccbbaa998877",
                first_seen_timestamp=datetime(2013, 4, 12, 0, 0, 0, tzinfo=timezone.utc),
                is_known_debunked_narrative=True,
                source_context="Debunked WhatsApp paywall chain-letter forward",
            ),
        ]


content_repository = InMemoryContentRepository()
