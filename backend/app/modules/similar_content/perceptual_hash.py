"""Perceptual Image Hashing and similarity computation."""

import io
import logging

import httpx
import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


def compute_image_perceptual_hash(image_bytes: bytes) -> str | None:
    """Compute 64-bit perceptual hash (pHash) string from image byte buffer.

    pHash is robust against image resizing, compression, and minor gamma modifications.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(img)
        return str(phash)
    except Exception as exc:
        logger.warning("Failed to compute image perceptual hash: %s", exc)
        return None


async def fetch_and_hash_image(image_url: str, timeout: float = 6.0) -> str | None:
    """Download image from URL with graceful error handling and compute its pHash."""
    if not image_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(image_url)
            if resp.status_code == 200:
                return compute_image_perceptual_hash(resp.content)
            else:
                logger.warning("Image download failed from %s with status %d", image_url[:40], resp.status_code)
                return None
    except Exception as exc:
        logger.warning("Error fetching image for perceptual hashing: %s", exc)
        return None


def calculate_hash_hamming_distance(hash_a_hex: str, hash_b_hex: str) -> int | None:
    """Compute bitwise Hamming distance between two hexadecimal hash strings.

    Hamming Distance <= 6 typically indicates identical / recycled visual content.
    """
    if not hash_a_hex or not hash_b_hex:
        return None

    try:
        h_a = imagehash.hex_to_hash(hash_a_hex)
        h_b = imagehash.hex_to_hash(hash_b_hex)
        return int(h_a - h_b)
    except Exception as exc:
        logger.warning("Error comparing hash hamming distance: %s", exc)
        return None


def hash_distance_to_similarity(hamming_distance: int | None, max_bits: int = 64) -> float:
    """Convert Hamming distance into normalized visual similarity score [0.0, 1.0]."""
    if hamming_distance is None:
        return 0.0
    dist = max(0, min(max_bits, hamming_distance))
    return round(float(1.0 - (dist / max_bits)), 4)
