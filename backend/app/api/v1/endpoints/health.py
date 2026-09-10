"""Health check endpoint router."""

from app.schemas.response import HealthCheckResponse
from fastapi import APIRouter, status

router = APIRouter(prefix="", tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Returns backend service health status and identifier.",
)
async def health_check() -> HealthCheckResponse:
    """Service health verification."""
    return HealthCheckResponse(
        status="ok",
        service="social-guard",
        version="0.1.0",
    )
