from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    query: str
    duration: Optional[str] = "medium"

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
