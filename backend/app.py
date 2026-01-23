"""
FastAPI application for Edu Video Recommender.
Migrated from Flask to FastAPI for async support and type safety.
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from backend import auth
from backend.database import get_db, init_db, test_connection
from backend.schemas import (
    HealthResponse,
    RecommendationResponse,
    VideoResult,
)
from scraper.semantic_search import log_search, recommend

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events.
    """
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # In production, we might want to prevent startup if DB is critical,
        # but for now we log and proceed (or re-raise to crash).
        # User requested fail-fast for secrets, implies we should fail fast here too.
        raise
    
    yield
    
    logger.info("Shutting down...")

# --- App Definition ---
app = FastAPI(
    title="Edu Video Recommender API",
    description="AI-powered educational video recommendation system",
    version="1.0.0",
    lifespan=lifespan
)

# --- CORS ---
origins_env = os.getenv("ALLOWED_ORIGINS")
if origins_env:
    origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
else:
    origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:6000",
        "http://127.0.0.1:6000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
app.include_router(auth.router)

# JWT Dependency Wrapper
async def get_current_user_id(request: Request) -> str:
    """
    Wrapper to get user ID from auth dependency.
    """
    try:
        # Extract the Authorization header manually
        authorization = request.headers.get("Authorization")
        user_claims = await auth.get_current_user(request, authorization)
        user_id = user_claims.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing user id in claims"
            )
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

@app.get("/")
async def root():
    return {"message": "Edu Video Recommender API", "status": "running"}

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    # Note: test_connection is sync, blocking.
    db_success, db_message = test_connection()
    
    # Simple ORM check
    orm_status = "unknown"
    try:
        # We need a fresh session here. 
        # Since get_db is a generator, we must iterate or use context manager if we adapted it.
        # But for quick check we can use the engine directly or the raw connection?
        # Let's use the generator manually for this check to be safe.

        from backend.database import get_db
        
        # Check connection via engine (already done in test_connection roughly)
        # Check models via session
        gen = get_db()
        session = next(gen)
        try:
            # Avoid importing models just for count if we can query generic
            # But let's verify ORM mapping works
            from backend import models
            video_count = session.query(models.Video).count()
            orm_status = f"working (videos: {video_count})"
        finally:
            # We must close/next
            gen.close()
            
    except Exception as e:
        orm_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="ok" if db_success else "error",
        message="Edu Video Recommender API",
        database="connected" if db_success else f"disconnected: {db_message}",
        orm=orm_status,
        environment=os.getenv('ENV', 'production')
    )

@app.get("/api/recommend", response_model=RecommendationResponse)
async def get_recommendations(
    query: str,
    duration: str = "medium",
    current_user: str = Depends(get_current_user_id),
    db: object = Depends(get_db)  # Injected session
):
    """
    Get video recommendations.
    """
    allowed_durations = {"any", "short", "medium", "long"}
    duration = duration.lower() if duration else "medium"
    if duration not in allowed_durations:
        duration = "medium"
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter is required"
        )
    
    try:
        # Pass the injected session to helper functions
        log_search(query, user_id=current_user, db_session=db)
        results = recommend(query, top_n=10, user_id=current_user, video_duration=duration, db_session=db)
        
        # Convert dict results to Pydantic models
        valid_results = []
        for r in results:
            # Ensure safety if keys missing
            valid_results.append(VideoResult(**r))

        return RecommendationResponse(results=valid_results)
    
    except Exception as e:
        logger.error(f"Error in /api/recommend: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

if __name__ == "__main__":
    import uvicorn
    # Use environment variables for host/port
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 6000)))
