"""Perceptual Image Hashing and similarity computation."""

import io
import logging

import httpx
import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


def compute_image_phash(image_bytes: bytes) -> str | None:
    """Compute 64-bit perceptual hash (pHash) string from image byte buffer.

    pHash uses DCT frequency analysis and is robust against image resizing, compression,
    and minor color/gamma adjustments.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(img)
        return str(phash)
    except Exception as exc:
        logger.warning("Failed to compute image pHash: %s", exc)
        return None


def compute_image_dhash(image_bytes: bytes) -> str | None:
    """Compute 64-bit difference hash (dHash) string from image byte buffer.

    dHash tracks gradient luminance differences between adjacent pixels and provides
    fast, structure-sensitive perceptual matching.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        dhash = imagehash.dhash(img)
        return str(dhash)
    except Exception as exc:
        logger.warning("Failed to compute image dHash: %s", exc)
        return None


def compute_image_perceptual_hash(image_bytes: bytes) -> str | None:
    """Backward-compatible alias for compute_image_phash."""
    return compute_image_phash(image_bytes)


def compute_image_hashes(image_bytes: bytes) -> dict[str, str | None]:
    """Compute both pHash and dHash for an image byte buffer."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        p = str(imagehash.phash(img))
        d = str(imagehash.dhash(img))
        return {"phash": p, "dhash": d}
    except Exception as exc:
        logger.warning("Failed to compute image hashes: %s", exc)
        return {"phash": None, "dhash": None}


async def fetch_and_hash_image(image_url: str, timeout: float = 6.0) -> str | None:
    """Download image from URL with SSRF protection and compute its pHash."""
    if not image_url:
        return None

    try:
        from app.utils.security import safe_fetch_image_bytes

        content = await safe_fetch_image_bytes(image_url, timeout=timeout)
        if content:
            return compute_image_phash(content)
        return None
    except Exception as exc:
        logger.warning("Error fetching image for perceptual hashing: %s", exc)
        return None


async def fetch_and_hash_image_full(image_url: str, timeout: float = 6.0) -> dict[str, str | None]:
    """Download image from URL with SSRF protection and compute both pHash and dHash."""
    if not image_url:
        return {"phash": None, "dhash": None}

    try:
        from app.utils.security import safe_fetch_image_bytes

        content = await safe_fetch_image_bytes(image_url, timeout=timeout)
        if content:
            return compute_image_hashes(content)
        return {"phash": None, "dhash": None}
    except Exception as exc:
        logger.warning("Error fetching image for perceptual hashing: %s", exc)
        return {"phash": None, "dhash": None}


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


def compare_visual_similarity(
    phash_a: str | None,
    phash_b: str | None,
    dhash_a: str | None = None,
    dhash_b: str | None = None,
) -> float:
    """Compute combined visual similarity score across pHash and dHash [0.0, 1.0]."""
    sims: list[float] = []

    if phash_a and phash_b:
        dist_p = calculate_hash_hamming_distance(phash_a, phash_b)
        if dist_p is not None:
            sims.append(hash_distance_to_similarity(dist_p))

    if dhash_a and dhash_b:
        dist_d = calculate_hash_hamming_distance(dhash_a, dhash_b)
        if dist_d is not None:
            sims.append(hash_distance_to_similarity(dist_d))

    if not sims:
        return 0.0

    return round(float(sum(sims) / len(sims)), 4)
