"""API v1 root router."""

from app.api.v1.endpoints.analyze import router as analyze_router
from app.api.v1.endpoints.health import router as health_router
from fastapi import APIRouter

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(analyze_router)
