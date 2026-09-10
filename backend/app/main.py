"""Social Guard Backend FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.config import settings
from app.schemas.response import HealthCheckResponse
from app.utils.exceptions import SocialGuardException
from app.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown routines."""
    logger.info("Initializing Social Guard API v%s in [%s] mode...", settings.APP_VERSION, settings.APP_ENV)
    yield
    logger.info("Shutting down Social Guard API...")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Explainable AI Framework for Social Media Content Verification",
        lifespan=lifespan,
    )

    # CORS configuration suitable for Chrome Extension & local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=r"^(chrome-extension://.*|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API Routers
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
        logger.warning("Validation error on [%s %s]: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "The incoming payload failed schema validation.",
                "details": exc.errors(),
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
