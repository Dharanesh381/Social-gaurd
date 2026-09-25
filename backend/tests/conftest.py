"""Pytest fixtures for backend test suite."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.db.models import Base

@pytest.fixture
def client():
    """Test client fixture for FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def async_db_session():
    """Create a fresh in-memory database and yield an active async session."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
def valid_post_payload():
    """Valid social media post verification payload fixture."""
    return {
        "post_id": "test_post_123",
        "platform": "twitter",
        "post_content": {
            "text": "Breaking news: New atmospheric data detected by Mars rover shows methane fluctuation.",
            "image_urls": ["https://example.com/mars_chart.png"],
            "hashtags": ["#Space", "#Mars", "#Science"],
            "timestamp": "2026-09-10T09:00:00Z",
        },
        "author": {
            "username": "science_reporter",
            "account_created_at": "2021-05-10T12:00:00Z",
            "followers_count": 12500,
            "following_count": 450,
            "total_posts": 1420,
            "recent_posts_frequency_per_day": 2.5,
        },
        "comments": [
            {
                "comment_id": "c_1",
                "author_id": "user_42",
                "text": "Fascinating results! Wonder if this correlates with previous orbit measurements.",
                "timestamp": "2026-09-10T09:15:00Z",
                "likes": 5,
            },
            {
                "comment_id": "c_2",
                "author_id": "user_88",
                "text": "Link to the primary scientific paper?",
                "timestamp": "2026-09-10T09:20:00Z",
                "likes": 2,
            },
        ],
    }
