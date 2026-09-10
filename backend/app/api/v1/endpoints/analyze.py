"""Analysis endpoint router with live verification pipeline."""

from app.db.session import get_db_session
from app.schemas.domain_models import AnalysisRequest, FinalAnalysisResult
from app.services.orchestrator import (
    AnalysisOrchestratorService,
    orchestrator_service,
)
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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
        "measures AI-generation probability, derives explainable factor rankings, and stores the session record."
    ),
)
async def analyze_social_post(
    payload: AnalysisRequest,
    service: AnalysisOrchestratorService = Depends(get_orchestrator_service),
    db: AsyncSession = Depends(get_db_session),
) -> FinalAnalysisResult:
    """Analyze incoming social media post."""
    return await service.analyze_post(request_data=payload, db_session=db)
