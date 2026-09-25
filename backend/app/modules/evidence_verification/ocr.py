"""Optional OCR (Optical Character Recognition) service interface."""

import io
import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class BaseOCRService(ABC):
    """Abstract interface for extracting text from image buffers or URLs."""

    @abstractmethod
    async def extract_text_from_url(self, image_url: str) -> str | None:
        """Download image and extract embedded text."""


class TesseractOCRService(BaseOCRService):
    """Tesseract and PIL-based OCR service with graceful fallback if binaries are missing."""

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout

    async def extract_text_from_url(self, image_url: str) -> str | None:
        """Download image and extract embedded text using pytesseract if available."""
        if not image_url:
            return None

        try:
            import pytesseract
            from PIL import Image

            from app.utils.security import safe_fetch_image_bytes

            raw_bytes = await safe_fetch_image_bytes(image_url, timeout=self.timeout)
            if not raw_bytes:
                return None

            img = Image.open(io.BytesIO(raw_bytes))
            extracted_text = pytesseract.image_to_string(img)
            cleaned = extracted_text.strip()
            logger.info("OCR extracted %d characters from image %s", len(cleaned), image_url[:40])
            return cleaned if cleaned else None

        except ImportError:
            logger.debug("pytesseract / PIL not installed or configured. Skipping OCR.")
            return None
        except Exception as exc:
            logger.warning("OCR extraction failed for %s: %s", image_url[:40], exc)
            return None


ocr_service = TesseractOCRService()
