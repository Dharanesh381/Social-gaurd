"""Social Guard Backend FastAPI Application Entrypoint."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.config import settings
from app.db.session import init_db_tables
from app.schemas.response import HealthCheckResponse
from app.utils.exceptions import SocialGuardException
from app.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown routines."""
    logger.info("Initializing Social Guard API v%s in [%s] mode...", settings.APP_VERSION, settings.APP_ENV)
    try:
        await init_db_tables()
    except Exception as exc:
        logger.error("Failed to initialize database tables on startup: %s", exc)

    # Warm up Sentence Transformer model so the first request does not suffer cold-start delay
    try:
        from app.modules.comment_analysis.similarity import get_sbert_model
        logger.info("Pre-warming Sentence-BERT model during application startup...")
        sbert = await asyncio.to_thread(get_sbert_model)
        if sbert is not None:
            await asyncio.to_thread(sbert.encode, ["Social Guard Warmup Text"], show_progress_bar=False)
            logger.info("Sentence-BERT model warmed up and ready in memory.")
    except Exception as exc:
        logger.warning("Sentence-BERT warmup encountered non-fatal error: %s", exc)

    yield
    logger.info("Shutting down Social Guard API...")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    enable_docs = (settings.APP_ENV.lower() != "production") or settings.DEBUG
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Explainable AI Framework for Social Media Content Verification",
        lifespan=lifespan,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    # CORS configuration suitable for Chrome Extension & local dev
    # Least-privilege methods and headers whitelist
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=r"^(chrome-extension://[a-zA-Z0-9]+|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?)$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],
    )

    # Include API Routers (mounted both at /api/v1 prefix and root for full compatibility)
    if settings.API_V1_PREFIX:
        app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
    app.include_router(api_v1_router)

    # Root health endpoint
    @app.get(
        "/health",
        response_model=HealthCheckResponse,
        tags=["Health"],
        summary="Service Health Check",
    )
    async def root_health_check() -> HealthCheckResponse:
        """Root health check returning service status."""
        return HealthCheckResponse(
            status="ok",
            service="social-guard",
            version=settings.APP_VERSION,
        )

    # Custom Exception Handlers
    @app.exception_handler(SocialGuardException)
    async def handle_domain_exception(request: Request, exc: SocialGuardException):
        logger.error("Domain exception on [%s %s]: %s", request.method, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Sanitize error items: do not echo raw unbounded input buffers back to client
        sanitized_details = []
        for err in exc.errors():
            sanitized_details.append({
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            })
        logger.warning("Validation error on [%s %s]: %s", request.method, request.url.path, sanitized_details)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "The incoming payload failed schema validation.",
                "details": sanitized_details,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        logger.exception("Unhandled exception on [%s %s]: %s", request.method, request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred during processing.",
            },
        )

    return app


app = create_application()
