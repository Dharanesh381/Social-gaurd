"""Pydantic schemas for analysis and health check responses."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="social-guard", description="Service identifier")
    version: str = Field(default="0.1.0", description="API version")


class CredibilityVerdict(str, Enum):
    """Fused categorical credibility verdict."""

    LIKELY_REAL = "LIKELY REAL"
    PROBABLY_REAL = "PROBABLY REAL"
    UNCERTAIN = "UNCERTAIN"
    PROBABLY_FAKE = "PROBABLY FAKE"
    LIKELY_FAKE = "LIKELY FAKE"
    NOT_IMPLEMENTED = "NOT IMPLEMENTED (PLACEHOLDER)"


class EvidenceState(str, Enum):
    """Module 2 evidence verification states."""

    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NO_FACT_CHECK_FOUND = "NO_FACT_CHECK_FOUND"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ModuleScoreBreakdown(BaseModel):
    """Score and metrics output for an individual module."""

    score: float | None = Field(None, description="Module score (0.0 to 100.0) or null if pending implementation")
    weight: float = Field(..., description="Weight coefficient in final score calculation")
    status: str = Field(default="pending_implementation", description="Module execution state")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Intermediate explainable metrics")


class PostAnalysisResponse(BaseModel):
    """Unified analysis response schema with XAI explainability metrics."""

    request_id: str = Field(..., description="Unique ID for this analysis session")
    status: str = Field(default="placeholder", description="Pipeline execution status")
    verdict: CredibilityVerdict = Field(
        default=CredibilityVerdict.NOT_IMPLEMENTED,
        description="Fused credibility verdict category",
    )
    credibility_score: float | None = Field(
        None, description="Overall fused credibility score (0-100), null during baseline placeholder phase"
    )
    ai_generated_probability: float | None = Field(
        None, description="Decoupled AI generation probability (0.0-1.0), null during placeholder phase"
    )
    summary_explanation: str = Field(
        ...,
        description="Human-readable explanation of findings and module contributions",
    )
    module_breakdown: dict[str, ModuleScoreBreakdown] = Field(
        default_factory=dict,
        description="Detailed breakdown of individual module scores and intermediate metrics",
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of completion",
    )
