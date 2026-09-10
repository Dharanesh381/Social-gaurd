"""Application configuration and environment settings."""


from pydantic import Field
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

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/social_guard_db"

    # ML & Model Defaults
    SBERT_MODEL_NAME: str = "all-MiniLM-L6-v2"
    DEVICE: str = "cpu"

    # Score Fusion Module Weights (Initial baseline)
    WEIGHT_COMMENTS: float = 0.20
    WEIGHT_EVIDENCE: float = 0.40
    WEIGHT_USER_BEHAVIOUR: float = 0.15
    WEIGHT_SIMILAR_CONTENT: float = 0.25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
