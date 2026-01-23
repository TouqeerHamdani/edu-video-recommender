"""
SQLAlchemy ORM models for the Edu Video Recommender.
- Video: YouTube videos with pgvector embeddings
- UserSearch: Track user search queries
- UserInteraction: Track user interactions (clicks, watches) with videos
"""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


class User(Base):
    """
    Reference to Supabase auth.users table for foreign key relationships.
    This table exists in Supabase but is managed by their auth system.
    """
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}
    id = Column(UUID(as_uuid=True), primary_key=True)
    UserSearches = relationship("UserSearch", back_populates="user")
    UserInteractions = relationship("UserInteraction", back_populates="user")
    # No other columns needed - just for FK reference


class Video(Base):
    
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail = Column(String(500), nullable=True)
    duration = Column(Integer, nullable=False)  # in seconds
    category = Column(String(50), nullable=True)
    upload_date = Column(String(50), nullable=True)  # ISO 8601 format
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    embedding = Column(Vector(384), nullable=True)  # MiniLM-L6-v2 produces 384-dim vectors (nullable for Phase 1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    interactions = relationship("UserInteraction", back_populates="video", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Video(id={self.id}, youtube_id={self.youtube_id}, title={self.title[:50]}...)>"


class UserSearch(Base):
    """
    Track user search queries for analytics and personalization.
    
    Columns:
    - id: Primary key
    - user_id: Supabase user UUID (from JWT token)
    - query: Search query text
    - search_time: Timestamp of search
    """
    
    __tablename__ = "user_searches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    search_time = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="UserSearches")
    
    def __repr__(self):
        return f"<UserSearch(id={self.id}, user_id={self.user_id}, query={self.query[:50]}...)>"


class UserInteraction(Base):
    """
    Track user interactions with videos (clicks, watches, ratings).
    Enables personalization in Phase 4.
    
    Columns:
    - id: Primary key
    - user_id: Supabase user UUID (from JWT token)
    - video_id: Foreign key to Video
    - interaction_type: 'click', 'watch', 'like', 'rating'
    - rating: 1-5 star rating (nullable, only for rating interactions)
    - interaction_time: Timestamp of interaction
    """
    
    __tablename__ = "user_interactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    interaction_type = Column(String(20), nullable=False)  # 'click', 'watch', 'like', 'rating'
    rating = Column(Integer, nullable=True)  # 1-5, only for rating interactions
    interaction_time = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    video = relationship("Video", back_populates="interactions")
    user = relationship("User", back_populates="UserInteractions")
    
    def __repr__(self):
        return f"<UserInteraction(id={self.id}, user_id={self.user_id}, video_id={self.video_id}, type={self.interaction_type})>"
