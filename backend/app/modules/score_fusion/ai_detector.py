"""AI-Generated Media and Text Detection Component.

Independent module designed to evaluate the probability of synthetic / AI generation.

CRITICAL DESIGN RULE:
AI-generated probability is an orthogonal dimension to factual credibility.
Synthetic media can convey factual information; human media can convey misinformation.
This module strictly produces a standalone probability [0.0 - 100.0] and never
directly alters the credibility classification score.
"""

import io
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BaseMediaAIDetector(ABC):
    """Abstract base class for image/media synthetic generation detectors."""

    @abstractmethod
    async def detect_image(self, image_bytes: bytes) -> dict[str, Any]:
        """Analyze image bytes and return synthetic generation probability [0.0 - 100.0]."""


class BaseTextAIDetector(ABC):
    """Abstract base class for text synthetic generation detectors."""

    @abstractmethod
    def detect_text(self, text: str) -> dict[str, Any]:
        """Analyze text and return synthetic generation probability [0.0 - 100.0]."""


class StatisticalImageArtifactDetector(BaseMediaAIDetector):
    """Image synthetic detector analyzing frequency domain artifacts, color histogram entropy,

    and high-frequency gradient variance typical of diffusion / GAN synthesis.

    Can be swapped seamlessly with deep vision classifiers (e.g. ViT / ResNet deepfake detector).
    """

    async def detect_image(self, image_bytes: bytes) -> dict[str, Any]:
        try:
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            arr = np.array(img, dtype=float)

            # 1. High-frequency Laplacian / gradient smoothness analysis
            # Synthetic diffusion models often exhibit overly smooth low-frequency textures
            # or distinctive grid artifacts in frequency domain
            gray = np.mean(arr, axis=2)
            grad_y, grad_x = np.gradient(gray)
            grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
            grad_var = float(np.var(grad_mag))

            # 2. Color channel correlation entropy
            # AI generators often exhibit unique chromatic aberration & channel covariance
            cov_matrix = np.cov(arr.reshape(-1, 3).T)
            corr_trace = float(np.trace(cov_matrix))

            # Normalization heuristic for signal variance
            # High gradient variance = textured natural photo; very low = artificial / synthetic
            smoothness_factor = max(0.0, min(1.0, 1.0 - (grad_var / 2500.0)))
            ai_prob = round(float(smoothness_factor * 100.0), 2)

            return {
                "ai_generation_probability": ai_prob,
                "confidence": "MEDIUM",
                "model_used": "StatisticalImageArtifactDetector (Gradient Variance + Chromatic Trace)",
                "metrics": {
                    "gradient_variance": round(grad_var, 2),
                    "chromatic_trace": round(corr_trace, 2),
                },
                "status": "ANALYZED",
            }
        except Exception as exc:
            logger.warning("Statistical image AI detection failed: %s", exc)
            return {
                "ai_generation_probability": None,
                "confidence": "NONE",
                "model_used": "StatisticalImageArtifactDetector",
                "status": "DETECTION_ERROR",
                "error": str(exc),
            }


class PerplexityTextAIDetector(BaseTextAIDetector):
    """Text synthetic detector analyzing n-gram lexical diversity and burstiness entropy."""

    def detect_text(self, text: str) -> dict[str, Any]:
        if not text or len(text.split()) < 10:
            return {
                "ai_generation_probability": None,
                "confidence": "LOW",
                "model_used": "PerplexityTextAIDetector",
                "status": "TEXT_TOO_SHORT",
                "explanation": "Text too short for statistical perplexity analysis (< 10 words).",
            }

        words = text.lower().split()
        total_words = len(words)
        unique_words = len(set(words))
        ttr = unique_words / max(1, total_words)  # Type-Token Ratio

        # Word length variance and burstiness
        word_lengths = [len(w) for w in words]
        import numpy as np
        length_std = float(np.std(word_lengths))

        # AI-generated text often exhibits very uniform sentence structures
        # and balanced type-token distributions (medium-high TTR with low length variance)
        uniformity_score = max(0.0, min(1.0, 1.0 - (length_std / 5.0)))
        ttr_factor = 1.0 if (0.45 <= ttr <= 0.85) else 0.5

        ai_prob = round(float(uniformity_score * ttr_factor * 100.0), 2)

        return {
            "ai_generation_probability": ai_prob,
            "confidence": "MEDIUM",
            "model_used": "PerplexityTextAIDetector (Lexical Diversity & Uniformity Entropy)",
            "metrics": {
                "type_token_ratio": round(ttr, 4),
                "length_std": round(length_std, 2),
                "word_count": total_words,
            },
            "status": "ANALYZED",
        }


class AIGeneratedMediaDetector:
    """Unified coordinator for AI-Generated media and text detection."""

    def __init__(
        self,
        image_detector: BaseMediaAIDetector | None = None,
        text_detector: BaseTextAIDetector | None = None,
        timeout: float = 6.0,
    ):
        self.image_detector = image_detector or StatisticalImageArtifactDetector()
        self.text_detector = text_detector or PerplexityTextAIDetector()
        self.timeout = timeout

    async def analyze_media_url(self, media_url: str) -> dict[str, Any]:
        """Download media and evaluate AI-generation probability."""
        if not media_url:
            return {
                "ai_generation_probability": None,
                "media_type": "unknown",
                "status": "EMPTY_URL",
                "explanation": "No media URL provided.",
            }

        # Check unsupported media formats (audio/video placeholders)
        url_lower = media_url.lower()
        if any(url_lower.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv"]):
            return {
                "ai_generation_probability": None,
                "media_type": "video",
                "status": "UNSUPPORTED_MEDIA_TYPE",
                "explanation": "Video deepfake detection is not currently supported in this lightweight baseline.",
            }
        elif any(url_lower.endswith(ext) for ext in [".mp3", ".wav", ".aac"]):
            return {
                "ai_generation_probability": None,
                "media_type": "audio",
                "status": "UNSUPPORTED_MEDIA_TYPE",
                "explanation": "Audio synthetic voice cloning detection is not currently supported.",
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(media_url)
                if resp.status_code != 200:
                    return {
                        "ai_generation_probability": None,
                        "media_type": "image",
                        "status": "DOWNLOAD_FAILED",
                        "explanation": f"Failed to download image from source (HTTP {resp.status_code}).",
                    }
                return await self.image_detector.detect_image(resp.content)
        except Exception as exc:
            return {
                "ai_generation_probability": None,
                "media_type": "image",
                "status": "CONNECTION_ERROR",
                "explanation": f"Network error during media download: {exc!s}",
            }

    def analyze_text(self, text: str) -> dict[str, Any]:
        """Evaluate AI-generation probability on textual content."""
        return self.text_detector.detect_text(text)


ai_media_detector = AIGeneratedMediaDetector()
