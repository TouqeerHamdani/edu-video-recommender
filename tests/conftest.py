"""
Shared test fixtures for the Edu Video Recommender API.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment before importing app
os.environ["ENV"] = "development"

from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock the Supabase client."""
    with patch("backend.auth.supabase") as mock:
        yield mock


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    mock_session = MagicMock()
    with patch("backend.database.get_db") as mock_get_db:
        mock_get_db.return_value = iter([mock_session])
        yield mock_session


@pytest.fixture
def auth_headers(mock_supabase):
    """
    Create valid auth headers with a mocked JWT.
    Returns headers dict with Authorization bearer token.
    """
    # Mock JWT verification to return valid claims
    with patch("backend.auth.get_current_user") as mock_auth:
        mock_auth.return_value = {
            "id": "test-user-123",
            "email": "test@example.com",
            "role": "authenticated"
        }
        yield {"Authorization": "Bearer fake-valid-token"}


@pytest.fixture
def sample_videos():
    """Sample video data matching VideoResult schema."""
    return [
        {
            "video_id": "abc123",
            "title": "Introduction to Python",
            "description": "Learn Python basics",
            "thumbnail": "https://img.youtube.com/vi/abc123/hqdefault.jpg",
            "channel": "Python Academy",
            "link": "https://www.youtube.com/watch?v=abc123",
            "score": 0.95,
            "views": 10000,
            "likes": 500
        },
        {
            "video_id": "def456",
            "title": "Advanced Machine Learning",
            "description": "Deep dive into ML algorithms",
            "thumbnail": "https://img.youtube.com/vi/def456/hqdefault.jpg",
            "channel": "ML Masters",
            "link": "https://www.youtube.com/watch?v=def456",
            "score": 0.88,
            "views": 5000,
            "likes": 300
        }
    ]
