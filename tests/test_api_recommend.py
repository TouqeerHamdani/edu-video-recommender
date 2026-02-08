"""
Tests for /api/recommend endpoint.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.app import app, get_current_user_id


# Override auth dependency for testing
async def mock_get_user_id():
    return "test-user-123"


class TestRecommendEndpoint:
    """Tests for the recommendation endpoint."""

    def test_recommend_requires_auth(self, client):
        """GET /api/recommend without auth should return 401."""
        response = client.get("/api/recommend", params={"query": "python"})
        assert response.status_code == 401

    def test_recommend_returns_results(self, client, sample_videos):
        """GET /api/recommend with valid query returns video results."""
        # Override auth dependency
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        with patch("backend.app.recommend") as mock_recommend, \
             patch("backend.app.log_search") as mock_log:
            mock_recommend.return_value = sample_videos

            response = client.get(
                "/api/recommend",
                params={"query": "python tutorial"},
                headers={"Authorization": "Bearer fake-token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert len(data["results"]) == 2

        # Clean up override
        app.dependency_overrides.clear()

    def test_recommend_empty_query_returns_400(self, client):
        """GET /api/recommend with empty query should return 400."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        with patch("backend.app.recommend") as mock_recommend, \
             patch("backend.app.log_search") as mock_log:
            response = client.get(
                "/api/recommend",
                params={"query": ""},
                headers={"Authorization": "Bearer fake-token"}
            )

            assert response.status_code == 400

        app.dependency_overrides.clear()

    def test_recommend_logs_search(self, client):
        """Recommend endpoint should log user searches."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        with patch("backend.app.recommend") as mock_recommend, \
             patch("backend.app.log_search") as mock_log:
            mock_recommend.return_value = []

            client.get(
                "/api/recommend",
                params={"query": "machine learning"},
                headers={"Authorization": "Bearer fake-token"}
            )

            # Verify log_search was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[0][0] == "machine learning"
            assert call_args[1]["user_id"] == "test-user-123"

        app.dependency_overrides.clear()

    def test_recommend_duration_filter(self, client):
        """Recommend should pass duration filter to search."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        with patch("backend.app.recommend") as mock_recommend, \
             patch("backend.app.log_search") as mock_log:
            mock_recommend.return_value = []

            client.get(
                "/api/recommend",
                params={"query": "python", "duration": "short"},
                headers={"Authorization": "Bearer fake-token"}
            )

            mock_recommend.assert_called_once()
            call_kwargs = mock_recommend.call_args[1]
            assert call_kwargs["video_duration"] == "short"

        app.dependency_overrides.clear()

    def test_recommend_invalid_duration_defaults_to_medium(self, client):
        """Invalid duration should default to 'medium'."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        with patch("backend.app.recommend") as mock_recommend, \
             patch("backend.app.log_search") as mock_log:
            mock_recommend.return_value = []

            client.get(
                "/api/recommend",
                params={"query": "python", "duration": "invalid"},
                headers={"Authorization": "Bearer fake-token"}
            )

            call_kwargs = mock_recommend.call_args[1]
            assert call_kwargs["video_duration"] == "medium"

        app.dependency_overrides.clear()


class TestRecommendErrorHandling:
    """Tests for error handling in recommend endpoint."""

    def test_recommend_internal_error_returns_500(self, client):
        """Internal errors should return 500."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        with patch("backend.app.recommend") as mock_recommend, \
             patch("backend.app.log_search") as mock_log:
            mock_recommend.side_effect = Exception("Database connection failed")

            response = client.get(
                "/api/recommend",
                params={"query": "python"},
                headers={"Authorization": "Bearer fake-token"}
            )

            assert response.status_code == 500
            assert "error" in response.json()

        app.dependency_overrides.clear()
