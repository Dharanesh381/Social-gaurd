"""SQLAlchemy Database Models for Social Guard."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class UserModel(Base):
    """Author / User Profile entity table."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(150), unique=True, index=True, nullable=False)
    account_age_days = Column(Integer, nullable=True)
    followers = Column(Integer, default=0, nullable=False)
    following = Column(Integer, default=0, nullable=False)
    posts_per_day = Column(Float, default=0.0, nullable=True)
    comments_per_day = Column(Float, default=0.0, nullable=True)
    engagement_rate = Column(Float, nullable=True)
    duplicate_content_ratio = Column(Float, nullable=True)
    hashtag_repetition_rate = Column(Float, nullable=True)
    raw_behaviour_metadata = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    posts = relationship("PostModel", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("CommentModel", back_populates="author")

    __table_args__ = (
        Index("idx_users_username_followers", "username", "followers"),
    )


class PostModel(Base):
    """Target Social Media Post entity table."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    platform_post_id = Column(String(100), index=True, nullable=True)
    platform = Column(String(50), default="generic", index=True, nullable=False)
    text = Column(Text, nullable=False)
    hashtags = Column(JSON, default=list, nullable=False)
    media_urls = Column(JSON, default=list, nullable=False)
    post_timestamp = Column(DateTime(timezone=True), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    author = relationship("UserModel", back_populates="posts")
    comments = relationship("CommentModel", back_populates="post", cascade="all, delete-orphan")
    evidence_items = relationship("EvidenceModel", back_populates="post", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResultModel", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_posts_platform_timestamp", "platform", "post_timestamp"),
    )


class CommentModel(Base):
    """Comments associated with a Post entity table."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    comment_platform_id = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    likes = Column(Integer, default=0, nullable=False)
    emojis = Column(JSON, default=list, nullable=False)
    emoji_count = Column(Integer, default=0, nullable=False)
    comment_timestamp = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    post = relationship("PostModel", back_populates="comments")
    author = relationship("UserModel", back_populates="comments")


class EvidenceModel(Base):
    """Extracted claims, fact-check matches, and source credibility records."""

    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False, index=True)
    status = Column(String(50), default="NO_FACT_CHECK_FOUND", nullable=False)  # SUPPORTED, CONTRADICTED, etc.
    publisher = Column(String(150), nullable=True, index=True)
    publisher_url = Column(String(500), nullable=True)
    raw_rating = Column(String(100), nullable=True)
    normalized_truth_score = Column(Float, nullable=True)
    source_credibility_weight = Column(Float, nullable=True)
    ocr_extracted_text = Column(Text, nullable=True)
    raw_response_metadata = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    post = relationship("PostModel", back_populates="evidence_items")


class AnalysisResultModel(Base):
    """Consolidated Social Guard Verification Session and XAI Diagnostic Record."""

    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(String(100), unique=True, index=True, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Consolidated Results
    final_score = Column(Float, nullable=False, index=True)
    classification = Column(String(50), nullable=False, index=True)
    ai_generated_probability = Column(Float, nullable=True)
    confidence_level = Column(String(20), default="MEDIUM", nullable=False)
    confidence_interval_low = Column(Float, nullable=True)
    confidence_interval_high = Column(Float, nullable=True)

    # Module Individual Normalized Scores (0 - 100)
    comment_score = Column(Float, nullable=True)
    evidence_score = Column(Float, nullable=True)
    behaviour_score = Column(Float, nullable=True)
    similarity_score = Column(Float, nullable=True)

    # Full Explainable Diagnostics & JSON Dictionaries
    explanation_summary = Column(Text, nullable=False)
    positive_factors = Column(JSON, default=list, nullable=False)
    negative_factors = Column(JSON, default=list, nullable=False)
    module_breakdowns = Column(JSON, default=dict, nullable=False)
    flags = Column(JSON, default=list, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    post = relationship("PostModel", back_populates="analysis_results")

    __table_args__ = (
        Index("idx_analysis_classification_score", "classification", "final_score"),
    )
