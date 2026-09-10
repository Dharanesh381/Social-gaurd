"""Comprehensive Pydantic domain schemas for Social Guard.

Models defined here cover:
- Core Inputs: Media, UserProfile, Comment, SocialMediaPost, AnalysisRequest
- Module Intermediate & Output Results:
  - CommentAnalysisResult (Module 1)
  - EvidenceAnalysisResult (Module 2)
  - BehaviourAnalysisResult (Module 3)
  - SimilarContentResult (Module 4)
  - ScoreFusionResult (Module 5)
  - FinalAnalysisResult (Consolidated Output)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

# ==============================================================================
# 1. ENUMS & CONSTANTS
# ==============================================================================

class MediaType(str, Enum):
    """Supported attached media types."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


class CredibilityClassification(str, Enum):
    """Final fused credibility classification bands."""
    LIKELY_REAL = "LIKELY REAL"       # 80 - 100
    PROBABLY_REAL = "PROBABLY REAL"   # 60 - 79
    UNCERTAIN = "UNCERTAIN"           # 40 - 59
    PROBABLY_FAKE = "PROBABLY FAKE"   # 20 - 39
    LIKELY_FAKE = "LIKELY FAKE"       # 0 - 19
    PENDING = "PENDING_EVALUATION"


class EvidenceVerificationState(str, Enum):
    """Evidence verification states for Module 2."""
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NO_FACT_CHECK_FOUND = "NO_FACT_CHECK_FOUND"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_EVALUATED = "NOT_EVALUATED"


# ==============================================================================
# 2. CORE INPUT DOMAIN MODELS
# ==============================================================================

class Media(BaseModel):
    """Attached media entity (image, video, etc.)."""
    url: HttpUrl = Field(..., description="Publicly accessible URL to media resource")
    media_type: MediaType = Field(default=MediaType.IMAGE, description="Type of media asset")
    ocr_extracted_text: str | None = Field(
        None, description="Pre-extracted text from image or frame if available"
    )
    perceptual_hash: str | None = Field(
        None, description="Pre-calculated perceptual hash if available"
    )


class UserProfile(BaseModel):
    """Public user profile & behavioral metadata."""
    username: str = Field(..., min_length=1, max_length=150, description="User handle or unique username")
    account_age_days: int | None = Field(
        None, ge=0, description="Account longevity in total days"
    )
    account_created_at: datetime | None = Field(
        None, description="Exact account creation timestamp"
    )
    followers: int = Field(default=0, ge=0, description="Total followers count")
    following: int = Field(default=0, ge=0, description="Total following count")
    posts_per_day: float | None = Field(
        default=0.0, ge=0.0, description="Average posts published per day"
    )
    comments_per_day: float | None = Field(
        default=0.0, ge=0.0, description="Average comments authored per day"
    )
    average_posting_interval_seconds: float | None = Field(
        None, ge=0.0, description="Average interval between consecutive posts in seconds"
    )
    engagement_rate: float | None = Field(
        None, ge=0.0, description="Engagement rate (e.g., (likes + reposts) / followers)"
    )
    duplicate_content_ratio: float | None = Field(
        None, ge=0.0, le=1.0, description="Ratio of repeated identical posts in recent timeline"
    )
    hashtag_repetition_rate: float | None = Field(
        None, ge=0.0, le=1.0, description="Repetition rate of specific hashtags in timeline"
    )


class Comment(BaseModel):
    """Social media comment on a target post."""
    comment_id: str | None = Field(None, description="Unique identifier for the comment")
    text: str = Field(..., min_length=1, max_length=10000, description="Text body of the comment")
    timestamp: datetime | None = Field(None, description="Comment publication timestamp")
    author: UserProfile | None = Field(
        None, description="Optional profile metadata for the commenter"
    )
    author_id: str | None = Field(
        None, description="Optional identifier or username of the commenter"
    )
    likes: int = Field(default=0, ge=0, description="Number of likes / upvotes")
    emojis: list[str] = Field(
        default_factory=list, description="Extracted list of emojis present in the comment"
    )
    emoji_count: int | None = Field(
        None, ge=0, description="Total count of emojis extracted"
    )

    @model_validator(mode="after")
    def calculate_emoji_count(self) -> "Comment":
        """Automatically set emoji_count if not explicitly provided."""
        if self.emoji_count is None and self.emojis is not None:
            self.emoji_count = len(self.emojis)
        return self


class SocialMediaPost(BaseModel):
    """Target social media post entity."""
    post_id: str | None = Field(None, description="Platform unique post ID")
    platform: str = Field(
        default="generic", description="Origin platform (e.g. twitter, reddit, facebook, generic)"
    )
    text: str = Field(..., min_length=1, max_length=50000, description="Main text body of the post")
    hashtags: list[str] = Field(default_factory=list, description="List of hashtags")
    media: list[Media] = Field(default_factory=list, description="List of attached media entities")
    timestamp: datetime | None = Field(None, description="Post publication timestamp")
    author: UserProfile | None = Field(
        None, description="Author/user profile information"
    )
    comments: list[Comment] = Field(
        default_factory=list, description="Extracted comments associated with the post"
    )

    @field_validator("platform")
    @classmethod
    def normalize_platform(cls, v: str) -> str:
        return v.strip().lower() if v else "generic"

    @field_validator("hashtags")
    @classmethod
    def clean_hashtags(cls, tags: list[str]) -> list[str]:
        cleaned = []
        for tag in tags:
            tag = tag.strip()
            if tag:
                cleaned.append(tag if tag.startswith("#") else f"#{tag}")
        return cleaned


class AnalysisRequest(BaseModel):
    """Top-level verification request model."""
    request_id: str | None = Field(None, description="Optional client-provided correlation ID")
    post: SocialMediaPost = Field(..., description="The social media post to verify")
    custom_weights: dict[str, float] | None = Field(
        None,
        description="Optional custom weights override for M1-M4 (must sum to 1.0)",
    )


# ==============================================================================
# 3. MODULE RESULTS & INTERMEDIATE METRICS MODELS
# ==============================================================================

class BaseModuleResult(BaseModel):
    """Base interface for all analytical module outputs."""
    module_name: str = Field(..., description="Identifying name of the module")
    score: float | None = Field(
        None, ge=0.0, le=100.0, description="Normalized score (0.0 to 100.0)"
    )
    status: str = Field(default="completed", description="Execution status of the module")
    intermediate_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Detailed granular metrics and diagnostic signals"
    )
    error: str | None = Field(None, description="Error message if module execution failed")


class CommentAnalysisResult(BaseModuleResult):
    """Module 1: Comment Analysis Engine Result."""
    module_name: str = Field(default="comment_analysis", description="Module identifier")
    total_comments_analyzed: int = Field(default=0, ge=0)
    duplicate_comment_ratio: float | None = Field(None, ge=0.0, le=1.0)
    semantic_similarity_mean: float | None = Field(None, ge=0.0, le=1.0)
    emoji_entropy: float | None = Field(None, ge=0.0)
    temporal_burst_zscore: float | None = Field(None)
    temporal_burst_detected: bool = Field(default=False)
    abnormal_comment_activity: bool = Field(default=False)


class FactCheckMatch(BaseModel):
    """Individual fact-check item matched via Google Fact Check API."""
    claim: str = Field(..., description="The factual claim text")
    claimant: str | None = Field(None, description="Entity who stated the claim")
    publisher: str = Field(..., description="Fact-checking publisher organisation")
    publisher_url: str | None = Field(None, description="URL of the fact-check article")
    review_rating: str = Field(..., description="Raw rating verbatim from publisher")
    normalized_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized truth score (0=False, 1=True)"
    )


class EvidenceAnalysisResult(BaseModuleResult):
    """Module 2: Evidence-Based Verification Engine Result."""
    module_name: str = Field(default="evidence_verification", description="Module identifier")
    state: EvidenceVerificationState = Field(
        default=EvidenceVerificationState.NO_FACT_CHECK_FOUND,
        description="Categorical evidence verification state",
    )
    extracted_claims: list[str] = Field(default_factory=list)
    matched_fact_checks: list[FactCheckMatch] = Field(default_factory=list)
    source_credibility_score: float | None = Field(None, ge=0.0, le=1.0)
    ocr_extracted_text: str | None = Field(None)


class BehaviourAnalysisResult(BaseModuleResult):
    """Module 3: User Behaviour Analysis Engine Result."""
    module_name: str = Field(default="user_behaviour", description="Module identifier")
    is_anomalous: bool = Field(default=False, description="Whether user behaviour is an anomaly")
    isolation_forest_score: float | None = Field(None, description="Raw Isolation Forest score")
    follower_following_ratio: float | None = Field(None, ge=0.0)
    posting_velocity_zscore: float | None = Field(None)
    engagement_rate: float | None = Field(None, ge=0.0)
    rule_penalties_applied: list[str] = Field(default_factory=list)


class SimilarContentResult(BaseModuleResult):
    """Module 4: Similar Content & Hashtag Analysis Result."""
    module_name: str = Field(default="similar_content", description="Module identifier")
    semantic_similarity_max: float | None = Field(None, ge=0.0, le=1.0)
    perceptual_hash_matches_count: int = Field(default=0, ge=0)
    min_hamming_distance: int | None = Field(None, ge=0)
    recycled_content_detected: bool = Field(default=False)
    hashtag_coordination_score: float | None = Field(None, ge=0.0, le=1.0)
    temporal_delta_days: float | None = Field(None, ge=0.0)


# ==============================================================================
# 4. CONSOLIDATED & FUSION OUTPUT MODELS
# ==============================================================================

class ScoreFusionResult(BaseModel):
    """Module 5: Consolidated Score Fusion & Decision Result."""
    consolidated_score: float = Field(
        ..., ge=0.0, le=100.0, description="Final fused credibility score (0.0 to 100.0)"
    )
    classification: CredibilityClassification = Field(
        ..., description="Standardized 5-tier credibility category"
    )
    weights_applied: dict[str, float] = Field(
        ..., description="Weights applied across the 4 modules"
    )
    formula_applied: str = Field(
        default="0.20*M1 + 0.40*M2 + 0.15*M3 + 0.25*M4",
        description="Mathematical equation applied for score fusion",
    )


class FinalAnalysisResult(BaseModel):
    """Top-Level Social Guard Analysis Result."""
    request_id: str = Field(..., description="Unique verification session ID")
    consolidated_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Consolidated credibility score (0-100)"
    )
    classification: CredibilityClassification = Field(
        default=CredibilityClassification.PENDING,
        description="Categorical credibility verdict",
    )
    ai_generation_probability: float | None = Field(
        None, ge=0.0, le=1.0, description="Decoupled AI-generation likelihood (0.0 to 1.0)"
    )
    explanation: str = Field(
        ..., description="Comprehensive explainability summary for human interpretation"
    )
    module_scores: dict[str, float | None] = Field(
        default_factory=dict, description="Summary mapping of module name to normalized score"
    )
    module_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Full nested breakdown of all module outputs and intermediate metrics",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC completion timestamp",
    )
