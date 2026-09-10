"""Module 5: Score Fusion & Explainability Engine package."""

from app.modules.score_fusion.ai_detector import (
    AIGeneratedMediaDetector,
    BaseMediaAIDetector,
    BaseTextAIDetector,
    PerplexityTextAIDetector,
    StatisticalImageArtifactDetector,
    ai_media_detector,
)
from app.modules.score_fusion.engine import (
    DEFAULT_WEIGHTS,
    ScoreFusionEngine,
    classify_credibility_score,
    score_fusion_engine,
)
from app.modules.score_fusion.explainability import (
    ExplainabilityEngine,
    explainability_engine,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "AIGeneratedMediaDetector",
    "BaseMediaAIDetector",
    "BaseTextAIDetector",
    "ExplainabilityEngine",
    "PerplexityTextAIDetector",
    "ScoreFusionEngine",
    "StatisticalImageArtifactDetector",
    "ai_media_detector",
    "classify_credibility_score",
    "explainability_engine",
    "score_fusion_engine",
]
