"""
FastAPI application for Edu Video Recommender.
Migrated from Flask to FastAPI for async support and type safety.
"""

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import jwt
import os
import logging
from scraper.semantic_search import recommend, log_search
from backend.database import init_db, test_connection
from backend import models

# Pydantic models for request/response
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

# JWT settings
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET', 'your-supabase-jwt-secret')

# Create FastAPI app
app = FastAPI(
    title="Edu Video Recommender API",
    description="AI-powered educational video recommendation system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise

# JWT dependency
def get_current_user(request: Request) -> Optional[str]:
    """Extract user ID from JWT token."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid"
        )
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=['HS256'])
        user_id = payload.get('sub')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Routes
@app.get("/")
async def root():
    return {"message": "Edu Video Recommender API", "status": "running"}

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint with database and ORM status."""
    db_success, db_message = test_connection()
    db_status = "connected" if db_success else f"disconnected: {db_message}"
    
    # Check ORM functionality
    try:
        from backend.database import get_session
        session = get_session()
        video_count = session.query(models.Video).count()
        session.close()
        orm_status = f"working (videos: {video_count})"
    except Exception as e:
        orm_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="ok" if db_success else "error",
        message="Edu Video Recommender API",
        database=db_status,
        orm=orm_status,
        environment=os.getenv('FLASK_ENV', 'production')  # Keep for compatibility
    )

@app.get("/api/recommend", response_model=RecommendationResponse)
async def get_recommendations(
    query: str,
    duration: str = "medium",
    current_user: str = Depends(get_current_user)
):
    """Get video recommendations based on semantic search."""
    allowed_durations = {"any", "short", "medium", "long"}
    duration = duration.lower()
    if duration not in allowed_durations:
        duration = "medium"
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter is required"
        )
    
    try:
        # Check database connection
        if not test_connection()[0]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Log search and get recommendations
        log_search(query, user_id=current_user)
        results = recommend(query, top_n=10, user_id=current_user, video_duration=duration)
        
        return RecommendationResponse(results=results)
    
    except Exception as e:
        logging.error(f"Error in /api/recommend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
