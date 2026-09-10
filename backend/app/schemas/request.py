"""Pydantic schemas for verification requests."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class AuthorSchema(BaseModel):
    """Author profile metadata schema."""

    username: str = Field(..., min_length=1, max_length=100, description="Author handle or username")
    account_created_at: datetime | None = Field(None, description="Account creation timestamp")
    followers_count: int = Field(default=0, ge=0, description="Total followers count")
    following_count: int = Field(default=0, ge=0, description="Total following count")
    total_posts: int = Field(default=0, ge=0, description="Total lifetime posts")
    recent_posts_frequency_per_day: float | None = Field(
        default=0.0, ge=0.0, description="Average posts published per 24 hours"
    )


class CommentSchema(BaseModel):
    """Social media comment schema."""

    comment_id: str | None = Field(None, description="Unique identifier for the comment")
    author_id: str | None = Field(None, description="Identifier of the commenter")
    text: str = Field(..., min_length=1, max_length=5000, description="Comment body text")
    timestamp: datetime | None = Field(None, description="Comment publication timestamp")
    likes: int = Field(default=0, ge=0, description="Number of likes/upvotes on comment")


class PostContentSchema(BaseModel):
    """Main post content schema."""

    text: str = Field(..., min_length=1, max_length=20000, description="Main text body of the social media post")
    image_urls: list[HttpUrl] = Field(default_factory=list, description="Attached image URLs")
    hashtags: list[str] = Field(default_factory=list, description="Extracted hashtags")
    timestamp: datetime | None = Field(None, description="Post publication timestamp")


class PostAnalysisRequest(BaseModel):
    """Top-level schema for incoming post analysis requests."""

    post_id: str | None = Field(None, description="Source platform unique post ID")
    platform: str = Field(
        default="generic",
        description="Source social media platform (e.g. twitter, reddit, facebook, generic)",
    )
    post_content: PostContentSchema = Field(..., description="Post textual and visual content")
    author: AuthorSchema | None = Field(None, description="Public profile metadata of author")
    comments: list[CommentSchema] = Field(default_factory=list, description="Extracted list of comments")

    @field_validator("platform")
    @classmethod
    def normalize_platform(cls, v: str) -> str:
        """Normalize platform name to lowercase."""
        return v.strip().lower() if v else "generic"
