"""
Tests for POST /api/interactions endpoint.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.app import app, get_current_user_id


# Override auth dependency for testing
async def mock_get_user_id():
    return "test-user-123"


class TestInteractionEndpoint:
    """Tests for the interaction logging endpoint."""

    def test_interaction_requires_auth(self, client):
        """POST /api/interactions without auth should return 401."""
        response = client.post(
            "/api/interactions",
            json={"video_id": 1, "interaction_type": "click"},
        )
        assert response.status_code == 401

    def test_click_interaction_success(self, client):
        """Logging a click interaction for an existing video returns 201."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        fake_video = MagicMock(id=1)
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = fake_video

        def _set_id(obj):
            obj.id = 42
        mock_session.refresh.side_effect = _set_id

        with patch("backend.app.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])

            response = client.post(
                "/api/interactions",
                json={"video_id": 1, "interaction_type": "click"},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Interaction logged successfully"
        assert data["interaction_id"] == 42
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        app.dependency_overrides.clear()

    def test_watch_interaction_success(self, client):
        """Logging a watch interaction returns 201."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        fake_video = MagicMock(id=1)
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = fake_video

        def _set_id(obj):
            obj.id = 99
        mock_session.refresh.side_effect = _set_id

        with patch("backend.app.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])

            response = client.post(
                "/api/interactions",
                json={"video_id": 1, "interaction_type": "watch"},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 201
        assert response.json()["interaction_id"] == 99

        app.dependency_overrides.clear()

    def test_rating_interaction_success(self, client):
        """Rating interaction with a valid rating returns 201."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        fake_video = MagicMock(id=1)
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = fake_video

        def _set_id(obj):
            obj.id = 7
        mock_session.refresh.side_effect = _set_id

        with patch("backend.app.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])

            response = client.post(
                "/api/interactions",
                json={"video_id": 1, "interaction_type": "rating", "rating": 4},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 201
        assert response.json()["interaction_id"] == 7

        app.dependency_overrides.clear()

    def test_rating_without_value_rejected(self, client):
        """Rating interaction without a rating value should be 422."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        response = client.post(
            "/api/interactions",
            json={"video_id": 1, "interaction_type": "rating"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

        app.dependency_overrides.clear()

    def test_rating_out_of_range_rejected(self, client):
        """Rating outside 1-5 should be rejected."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        response = client.post(
            "/api/interactions",
            json={"video_id": 1, "interaction_type": "rating", "rating": 0},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/interactions",
            json={"video_id": 1, "interaction_type": "rating", "rating": 6},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

        app.dependency_overrides.clear()

    def test_invalid_interaction_type_rejected(self, client):
        """Unknown interaction type should be 422."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        response = client.post(
            "/api/interactions",
            json={"video_id": 1, "interaction_type": "bookmark"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

        app.dependency_overrides.clear()

    def test_video_not_found_returns_404(self, client):
        """Interaction for a nonexistent video returns 404."""
        app.dependency_overrides[get_current_user_id] = mock_get_user_id

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch("backend.app.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_session])

            response = client.post(
                "/api/interactions",
                json={"video_id": 9999, "interaction_type": "click"},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["error"]

        app.dependency_overrides.clear()
