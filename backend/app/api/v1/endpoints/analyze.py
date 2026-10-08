"""Analysis endpoint router with live verification pipeline."""

from app.schemas.domain_models import AnalysisRequest, FinalAnalysisResult
from app.services.orchestrator import (
    AnalysisOrchestratorService,
    orchestrator_service,
)
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="", tags=["Analysis"])


def get_orchestrator_service() -> AnalysisOrchestratorService:
    """Dependency provider for the analysis orchestrator service."""
    return orchestrator_service


@router.post(
    "/analyze",
    response_model=FinalAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Validate post and perform full Explainable AI credibility analysis",
    description=(
        "Ingests social media post content, author metadata, attached media, and comments. "
        "Executes Modules 1-5 (Comment Analysis, Evidence Verification, User Behaviour, Similar Content, Score Fusion), "
        "measures AI-generation probability, derives explainable factor rankings, and returns results in memory."
    ),
)
async def analyze_social_post(
    payload: AnalysisRequest,
    service: AnalysisOrchestratorService = Depends(get_orchestrator_service),
) -> FinalAnalysisResult:
    """Analyze incoming social media post entirely in memory."""
    return await service.analyze_post(request_data=payload)
