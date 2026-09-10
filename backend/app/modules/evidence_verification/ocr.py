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

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(image_url)
                if resp.status_code != 200:
                    logger.warning("Failed to fetch image from %s (status %d)", image_url, resp.status_code)
                    return None

                img = Image.open(io.BytesIO(resp.content))
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
