import re
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


class RecommendationRequest(BaseModel):
    query: str
    duration: Optional[str] = "medium"


class InteractionRequest(BaseModel):
    video_id: str  # YouTube video ID from frontend
    interaction_type: Literal["click", "watch", "like", "rating"]
    rating: Optional[int] = None

    @field_validator("video_id")
    @classmethod
    def validate_youtube_id(cls, v):
        if not re.match(r'^[A-Za-z0-9_-]{11}$', v):
            raise ValueError("Invalid YouTube video ID format")
        return v

    @field_validator("rating")
    @classmethod
    def validate_rating_range(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v

    @model_validator(mode="after")
    def validate_rating_required(self):
        if self.interaction_type == "rating" and self.rating is None:
            raise ValueError("Rating is required for interaction_type 'rating'")
        return self


class InteractionResponse(BaseModel):
    message: str
    interaction_id: int

class VideoResult(BaseModel):
    video_id: str
    title: str
    description: Optional[str]
    thumbnail: Optional[str]
    channel: str
    link: str
    score: float
    views: Optional[int] = None
    likes: Optional[int] = None

class RecommendationResponse(BaseModel):
    results: List[VideoResult]

class HealthResponse(BaseModel):
    status: str
    message: str
    database: str
    orm: str
    environment: str
