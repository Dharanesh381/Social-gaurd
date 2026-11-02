"""Unit tests for AI-Generated Media and Text Detection Component."""

import io
import pytest
from PIL import Image

from app.modules.score_fusion.ai_detector import (
    AIGeneratedMediaDetector,
    PerplexityTextAIDetector,
    StatisticalImageArtifactDetector,
)


@pytest.fixture
def sample_image_bytes():
    """Create a sample in-memory RGB image byte buffer."""
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_statistical_image_detector(sample_image_bytes: bytes):
    """Test image artifact detection returns valid probability and metrics."""
    detector = StatisticalImageArtifactDetector()
    res = await detector.detect_image(sample_image_bytes)

    assert res["status"] == "ANALYZED"
    assert res["ai_generation_probability"] is not None
    assert 0.0 <= res["ai_generation_probability"] <= 100.0
    assert "gradient_variance" in res["metrics"]


def test_text_ai_detector_short_text():
    """Test text detector returns TEXT_TOO_SHORT on short phrases without crashing."""
    detector = PerplexityTextAIDetector()
    res = detector.detect_text("Too short")
    assert res["status"] == "TEXT_TOO_SHORT"
    assert res["ai_generation_probability"] is None


def test_text_ai_detector_longer_text():
    """Test text detector computes lexical uniformity on longer paragraphs."""
    detector = PerplexityTextAIDetector()
    long_text = (
        "Artificial intelligence and machine learning technologies continue to develop "
        "rapidly across multiple sectors including healthcare, education, and cybersecurity. "
        "These developments present notable benefits and challenges for researchers."
    )
    res = detector.detect_text(long_text)
    assert res["status"] == "ANALYZED"
    assert res["ai_generation_probability"] is not None
    assert 0.0 <= res["ai_generation_probability"] <= 100.0
    assert "type_token_ratio" in res["metrics"]


@pytest.mark.asyncio
async def test_unsupported_media_handling():
    """Test detector gracefully handles unsupported video or audio URLs."""
    coordinator = AIGeneratedMediaDetector()

    video_res = await coordinator.analyze_media_url("https://example.com/deepfake_video.mp4")
    assert video_res["status"] == "UNSUPPORTED_MEDIA_TYPE"
    assert video_res["media_type"] == "video"
    assert video_res["ai_generation_probability"] is None

    audio_res = await coordinator.analyze_media_url("https://example.com/voice_clone.wav")
    assert audio_res["status"] == "UNSUPPORTED_MEDIA_TYPE"
    assert audio_res["media_type"] == "audio"
    assert audio_res["ai_generation_probability"] is None


def test_ai_stylistic_differentiation():
    """Verify that formal AI discursive markers score significantly higher than human slang."""
    detector = PerplexityTextAIDetector()

    ai_text = (
        "Furthermore, comprehensive analysis indicates that artificial intelligence presents multifaceted paradigms. "
        "Consequently, one must take into consideration all relevant factors, highlighting the intricate nuances."
    )
    human_text = "yo bro tbh this is totally crazy lmao, no way this is actually real fr fr!!!"

    res_ai = detector.detect_text(ai_text)
    res_human = detector.detect_text(human_text)

    assert res_ai["status"] == "ANALYZED"
    assert res_human["status"] == "ANALYZED"
    assert res_ai["ai_generation_probability"] > 75.0
    assert res_human["ai_generation_probability"] < 25.0
    assert res_ai["ai_generation_probability"] > res_human["ai_generation_probability"] + 50.0


@pytest.mark.asyncio
async def test_image_generator_metadata():
    """Verify that images with generator parameters/signatures are identified as synthetic."""
    detector = StatisticalImageArtifactDetector()
    img = Image.new("RGB", (64, 64), color=(100, 100, 100))

    from PIL import PngImagePlugin
    meta = PngImagePlugin.PngInfo()
    meta.add_text("parameters", "A photorealistic cat in space, Midjourney v6 prompt")

    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)

    res = await detector.detect_image(buf.getvalue())
    assert res["status"] == "ANALYZED"
    assert res["ai_generation_probability"] >= 90.0
    assert res["metrics"]["generator_tag_detected"] is True
