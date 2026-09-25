"""Application configuration and environment settings."""


from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Social Guard API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # Security & CORS
    SECRET_KEY: str = "default-insecure-secret-key-change-me"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # External APIs
    GOOGLE_FACT_CHECK_API_KEY: str = Field(
        default="", description="Google Fact Check Tools API Key"
    )

    # Database (Defaults to SQLite for local development; override via DATABASE_URL in .env for PostgreSQL)
    DATABASE_URL: str = "sqlite+aiosqlite:///./social_guard.db"

    # ML & Model Defaults
    SBERT_MODEL_NAME: str = "all-MiniLM-L6-v2"
    DEVICE: str = "cpu"

    # Score Fusion Module Weights (Initial baseline)
    WEIGHT_COMMENTS: float = 0.20
    WEIGHT_EVIDENCE: float = 0.40
    WEIGHT_USER_BEHAVIOUR: float = 0.15
    WEIGHT_SIMILAR_CONTENT: float = 0.25

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Enforce production security rules: disable DEBUG and enforce strong secret."""
        if self.APP_ENV.lower() == "production":
            # In production, debug mode must default to False unless explicitly forced
            if self.SECRET_KEY == "default-insecure-secret-key-change-me":
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION: When APP_ENV=production, "
                    "SECRET_KEY must be configured with a strong production key."
                )
        return self

    def __repr__(self) -> str:
        """Mask sensitive keys in string representations to prevent secret leakage in logs."""
        fields = []
        for k, v in self.model_dump().items():
            if any(term in k.lower() for term in ("key", "secret", "token", "password")):
                fields.append(f"{k}='***'")
            else:
                fields.append(f"{k}={v!r}")
        return f"{self.__class__.__name__}({', '.join(fields)})"

    def __str__(self) -> str:
        return self.__repr__()


settings = Settings()

