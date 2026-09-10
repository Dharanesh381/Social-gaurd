"""Pydantic schemas package entry."""

from app.schemas.domain_models import (
    AnalysisRequest,
    BaseModuleResult,
    BehaviourAnalysisResult,
    Comment,
    CommentAnalysisResult,
    CredibilityClassification,
    EvidenceAnalysisResult,
    EvidenceVerificationState,
    FactCheckMatch,
    FinalAnalysisResult,
    Media,
    MediaType,
    ScoreFusionResult,
    SimilarContentResult,
    SocialMediaPost,
    UserProfile,
)
from app.schemas.request import (
    AuthorSchema,
    CommentSchema,
    PostAnalysisRequest,
    PostContentSchema,
)
from app.schemas.response import (
    CredibilityVerdict,
    EvidenceState,
    HealthCheckResponse,
    ModuleScoreBreakdown,
    PostAnalysisResponse,
)

__all__ = [
    # Core Domain Inputs
    "Media",
    "MediaType",
    "UserProfile",
    "Comment",
    "SocialMediaPost",
    "AnalysisRequest",
    # Domain Results
    "BaseModuleResult",
    "CommentAnalysisResult",
    "FactCheckMatch",
    "EvidenceAnalysisResult",
    "BehaviourAnalysisResult",
    "SimilarContentResult",
    "ScoreFusionResult",
    "FinalAnalysisResult",
    # Enums
    "CredibilityClassification",
    "EvidenceVerificationState",
    # API specific wrappers
    "AuthorSchema",
    "CommentSchema",
    "PostContentSchema",
    "PostAnalysisRequest",
    "HealthCheckResponse",
    "CredibilityVerdict",
    "EvidenceState",
    "ModuleScoreBreakdown",
    "PostAnalysisResponse",
]
