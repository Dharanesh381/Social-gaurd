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
    """Image synthetic detector analyzing frequency domain artifacts, color channel covariance,
    radial spectral falloff, gradient variance, and EXIF generator signatures typical of diffusion / GAN synthesis.

    Can be swapped seamlessly with deep vision classifiers (e.g. ViT / ResNet deepfake detector).
    """

    async def detect_image(self, image_bytes: bytes) -> dict[str, Any]:
        try:
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))

            # 1. EXIF and Metadata Inspection
            # Check for AI generator tags (Midjourney, DALL-E, Stable Diffusion, ComfyUI, Automatic1111)
            info_dict = img.info or {}
            has_generator_tag = False
            has_camera_exif = False

            ai_signatures = [
                "midjourney",
                "dall-e",
                "stablediffusion",
                "stable diffusion",
                "novelai",
                "comfyui",
                "parameters",
                "prompt",
            ]
            for k, v in info_dict.items():
                k_str = str(k).lower()
                v_str = str(v).lower()
                if any(sig in k_str or sig in v_str for sig in ai_signatures):
                    has_generator_tag = True
                    break

            exif_data = img.getexif() if hasattr(img, "getexif") else None
            if exif_data and len(exif_data) > 3:
                has_camera_exif = True

            if has_generator_tag:
                return {
                    "ai_generation_probability": 96.0,
                    "confidence": "HIGH",
                    "model_used": "StatisticalImageArtifactDetector (Metadata Generator Signature)",
                    "metrics": {
                        "gradient_variance": 0.0,
                        "chromatic_trace": 0.0,
                        "spectral_high_ratio": 0.0,
                        "generator_tag_detected": True,
                    },
                    "status": "ANALYZED",
                }

            # 2. Convert to RGB array
            rgb_img = img.convert("RGB")
            arr = np.array(rgb_img, dtype=float)
            h, w, _ = arr.shape

            if h < 16 or w < 16:
                return {
                    "ai_generation_probability": 15.0,
                    "confidence": "LOW",
                    "model_used": "StatisticalImageArtifactDetector",
                    "metrics": {
                        "gradient_variance": 0.0,
                        "chromatic_trace": 0.0,
                    },
                    "status": "ANALYZED",
                }

            # 3. Gradient smoothness analysis
            gray = np.mean(arr, axis=2)
            grad_y, grad_x = np.gradient(gray)
            grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
            grad_var = float(np.var(grad_mag))

            # 4. Color channel correlation & covariance
            reshaped = arr.reshape(-1, 3)
            cov_matrix = np.cov(reshaped.T)
            corr_trace = float(np.trace(cov_matrix))
            stddevs = np.std(reshaped, axis=0)
            if np.all(stddevs > 1e-4):
                corr_matrix = np.corrcoef(reshaped.T)
                mean_cross_corr = float((corr_matrix[0, 1] + corr_matrix[0, 2] + corr_matrix[1, 2]) / 3.0)
            else:
                mean_cross_corr = 0.5

            # 5. 2D FFT Frequency domain analysis (Radial power spectrum falloff & VAE upsampler grid artifacts)
            fshift = np.fft.fftshift(np.fft.fft2(gray))
            mag = np.abs(fshift) + 1e-6
            cy, cx = h // 2, w // 2
            y, x = np.ogrid[:h, :w]
            dist_from_center = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
            max_r = min(h, w) / 2.0

            low_mask = dist_from_center <= (max_r * 0.25)
            high_mask = dist_from_center >= (max_r * 0.70)
            total_energy = float(np.sum(mag))
            low_ratio = float(np.sum(mag[low_mask]) / total_energy) if total_energy > 0 else 0.5
            high_ratio = float(np.sum(mag[high_mask]) / total_energy) if total_energy > 0 else 0.0

            # 6. Synthesize statistical probability
            prob = 20.0  # Base natural baseline for web images

            if has_camera_exif:
                prob -= 12.0

            # Diffusion synthetic images often exhibit high cross-correlation (> 0.985)
            if mean_cross_corr > 0.985:
                prob += 22.0

            # Diffusion VAE upsamplers produce excessive high-frequency spectral energy (grid/checkerboard artifacts)
            if high_ratio > 0.25:
                prob += min(35.0, (high_ratio - 0.25) * 100.0)

            # Solid color / diagram / chart graphics: cap at natural baseline
            if grad_var < 5.0:
                prob = max(10.0, min(prob, 25.0))

            ai_prob = round(float(max(5.0, min(95.0, prob))), 2)

            return {
                "ai_generation_probability": ai_prob,
                "confidence": "MEDIUM",
                "model_used": "StatisticalImageArtifactDetector (2D FFT Spectrum + Chromatic Covariance + EXIF)",
                "metrics": {
                    "gradient_variance": round(grad_var, 2),
                    "chromatic_trace": round(corr_trace, 2),
                    "cross_channel_correlation": round(mean_cross_corr, 3),
                    "low_freq_ratio": round(low_ratio, 3),
                    "high_freq_ratio": round(high_ratio, 3),
                    "has_camera_exif": has_camera_exif,
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
    """Text synthetic detector analyzing stylometric markers, formal syntax, and lexical uniformity."""

    # Discursive transition markers characteristic of LLM synthesis
    AI_DISCURSIVE_PATTERNS = [
        r"\bdelve(?:s|d|ing)? into\b",
        r"\bfurthermore\b",
        r"\bmoreover\b",
        r"\bconsequently\b",
        r"\badditionally\b",
        r"\bin conclusion\b",
        r"\bin summary\b",
        r"\bto summarize\b",
        r"\bit is important to (?:note|remember|consider)\b",
        r"\bit is worth (?:noting|mentioning)\b",
        r"\bcomprehensive analysis\b",
        r"\bmultifaceted\b",
        r"\bparamount\b",
        r"\bpivotal role\b",
        r"\btestament to\b",
        r"\bbeacon of\b",
        r"\blandscape of\b",
        r"\brealm of\b",
        r"\bunderscores?\b",
        r"\bshed(?:s|ding)? light on\b",
        r"\bplays? a crucial role\b",
        r"\bpoised to\b",
        r"\bnotably\b",
        r"\bgroundbreaking\b",
        r"\bseamlessly\b",
        r"\bintricate\b",
        r"\bharnessing the power\b",
        r"\bfoster(?:ing)?\b",
        r"\bnavigating the\b",
        r"\bmeticulous(?:ly)?\b",
        r"\bunprecedented\b",
        r"\bnotwithstanding\b",
        r"\bholistic\b",
        r"\bparadigm shift\b",
        r"\btake into consideration\b",
    ]

    # Participial trailing clauses heavily favored by instruction-tuned LLMs
    PARTICIPIAL_CLAUSE_PATTERN = (
        r",\s+(?:providing|highlighting|underscoring|ensuring|demonstrating|offering|reflecting|showcasing|marking)\b"
    )

    # Human informal social media markers (strong negative indicators of AI generation)
    HUMAN_INFORMAL_PATTERNS = [
        r"\b(?:lol|lmao|rofl|smh|tbh|imo|imho|ngl|idk|omg|wtf|bruh|yall|y\'all|gonna|wanna|gotta|pls|plz|fr|rn)\b",
        r"\b(?:dude|bro|guyz|fellas)\b",
        r"[!?]{2,}",  # Repeated punctuation: !!, ???, !?!
        r"\b(?:dont|cant|wont|didnt|isnt|arent|ive|youre)\b",  # Unapostrophized informal typing
        r"\b(?:BREAKING|URGENT|WARNING|ATTENTION|SCAM|HOAX|SHOCKING|UNBELIEVABLE|ALERT)\b",  # Sensational shouting
    ]

    def detect_text(self, text: str) -> dict[str, Any]:
        if not text:
            return {
                "ai_generation_probability": None,
                "confidence": "LOW",
                "model_used": "PerplexityTextAIDetector",
                "status": "TEXT_TOO_SHORT",
                "explanation": "No text provided.",
            }

        import re
        import numpy as np

        words = re.findall(r"\b[a-zA-Z0-9_\'-]+\b", text)
        total_words = len(words)
        if total_words < 8:
            return {
                "ai_generation_probability": None,
                "confidence": "LOW",
                "model_used": "PerplexityTextAIDetector",
                "status": "TEXT_TOO_SHORT",
                "explanation": "Text too short for statistical stylometric analysis (< 8 words).",
            }

        lower_text = text.lower()
        unique_words = len(set(w.lower() for w in words))
        ttr = unique_words / max(1, total_words)

        # 1. AI stylistic marker hits
        ai_hits = sum(len(re.findall(p, lower_text)) for p in self.AI_DISCURSIVE_PATTERNS)
        participial_hits = len(re.findall(self.PARTICIPIAL_CLAUSE_PATTERN, lower_text))

        # 2. Human informal marker hits
        human_hits = sum(len(re.findall(p, text)) for p in self.HUMAN_INFORMAL_PATTERNS)

        # 3. Formality & word length distribution
        word_lens = [len(w) for w in words]
        avg_word_len = sum(word_lens) / total_words
        length_std = float(np.std(word_lens))
        long_words_ratio = sum(1 for w in words if len(w) >= 8) / total_words

        # 4. Sentence burstiness (variance of sentence lengths)
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        if len(sentences) > 1:
            s_lens = [len(s.split()) for s in sentences]
            s_std = float(np.std(s_lens))
            burstiness_discount = min(15.0, s_std * 1.5)
        else:
            burstiness_discount = 0.0

        # 5. Composite AI probability formula
        prob = 18.0  # Base natural social text baseline

        # Boost from AI markers and formal participial clauses
        prob += ai_hits * 28.0
        prob += participial_hits * 24.0

        # Formality boost (academic / elevated Latinate vocabulary)
        if avg_word_len >= 5.5:
            prob += min(30.0, (avg_word_len - 5.0) * 18.0)
        if long_words_ratio >= 0.20:
            prob += min(20.0, (long_words_ratio - 0.15) * 60.0)

        # Penalty from human informal markers and burstiness
        prob -= human_hits * 18.0
        prob -= burstiness_discount

        ai_prob = round(float(max(3.0, min(97.0, prob))), 2)

        confidence = "HIGH" if (ai_hits > 0 or ai_prob >= 70.0 or ai_prob <= 15.0) else "MEDIUM"

        return {
            "ai_generation_probability": ai_prob,
            "confidence": confidence,
            "model_used": "PerplexityTextAIDetector (Stylometrics, Formality & Lexical Entropy)",
            "metrics": {
                "type_token_ratio": round(ttr, 4),
                "length_std": round(length_std, 2),
                "avg_word_len": round(avg_word_len, 2),
                "long_words_ratio": round(long_words_ratio, 3),
                "word_count": total_words,
                "ai_markers_count": ai_hits,
                "human_markers_count": human_hits,
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
            from app.utils.security import safe_fetch_image_bytes

            raw_bytes = await safe_fetch_image_bytes(media_url, timeout=self.timeout)
            if not raw_bytes:
                return {
                    "ai_generation_probability": None,
                    "media_type": "image",
                    "status": "DOWNLOAD_FAILED",
                    "explanation": "Could not download image from source URL (timeout, blocked, or invalid format).",
                }
            return await self.image_detector.detect_image(raw_bytes)
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
