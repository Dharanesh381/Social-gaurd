"""Database session management and engine configuration."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Configure Async Engine using DATABASE_URL from settings
# Defaults to SQLite async for local testing/dev if PostgreSQL is not active
_db_url = getattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///./social_guard.db")

engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session with automatic rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            logger.error("Database session error: %s", exc)
            raise exc
        finally:
            await session.close()


async def init_db_tables(custom_engine=None) -> None:
    """Create all database tables on application startup."""
    active_engine = custom_engine or engine
    try:
        async with active_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Successfully initialized database tables.")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        raise exc
