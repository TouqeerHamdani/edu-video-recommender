"""
Tests for POST /api/interactions endpoint.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app import app, get_async_db, get_current_user_id


# Override auth dependency for testing
async def mock_get_user_id():
    return "test-user-123"


def _make_async_db(fake_video=None, interaction_id=None):
    """Return an async generator that yields a fully mocked AsyncSession."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # add() is sync on AsyncSession
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_video
    mock_session.execute.return_value = mock_result

    async def _set_id(obj):
        obj.id = interaction_id
    mock_session.refresh.side_effect = _set_id

    async def _override():
        yield mock_session

    return _override, mock_session


@pytest.fixture(autouse=False)
def auth_override():
    """Set mock auth dependency override and ensure cleanup even on failure."""
    app.dependency_overrides[get_current_user_id] = mock_get_user_id
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


class TestInteractionEndpoint:
    """Tests for the interaction logging endpoint."""

    def test_interaction_requires_auth(self, client):
        """POST /api/interactions without auth should return 401."""
        response = client.post(
            "/api/interactions",
            json={"video_id": "abc12345678", "interaction_type": "click"},
        )
        assert response.status_code == 401

    def test_click_interaction_success(self, client, auth_override):
        """Logging a click interaction for an existing video returns 201."""
        fake_video = MagicMock(id=1)
        db_override, mock_session = _make_async_db(fake_video=fake_video, interaction_id=42)
        app.dependency_overrides[get_async_db] = db_override
        try:
            response = client.post(
                "/api/interactions",
                json={"video_id": "abc12345678", "interaction_type": "click"},
                headers={"Authorization": "Bearer fake-token"},
            )
        finally:
            app.dependency_overrides.pop(get_async_db, None)

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Interaction logged successfully"
        assert data["interaction_id"] == 42
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_watch_interaction_success(self, client, auth_override):
        """Logging a watch interaction returns 201."""
        fake_video = MagicMock(id=1)
        db_override, _ = _make_async_db(fake_video=fake_video, interaction_id=99)
        app.dependency_overrides[get_async_db] = db_override
        try:
            response = client.post(
                "/api/interactions",
                json={"video_id": "abc12345678", "interaction_type": "watch"},
                headers={"Authorization": "Bearer fake-token"},
            )
        finally:
            app.dependency_overrides.pop(get_async_db, None)

        assert response.status_code == 201
        assert response.json()["interaction_id"] == 99

    def test_rating_interaction_success(self, client, auth_override):
        """Rating interaction with a valid rating returns 201."""
        fake_video = MagicMock(id=1)
        db_override, _ = _make_async_db(fake_video=fake_video, interaction_id=7)
        app.dependency_overrides[get_async_db] = db_override
        try:
            response = client.post(
                "/api/interactions",
                json={"video_id": "abc12345678", "interaction_type": "rating", "rating": 4},
                headers={"Authorization": "Bearer fake-token"},
            )
        finally:
            app.dependency_overrides.pop(get_async_db, None)

        assert response.status_code == 201
        assert response.json()["interaction_id"] == 7

    def test_rating_without_value_rejected(self, client, auth_override):
        """Rating interaction without a rating value should be 422."""
        response = client.post(
            "/api/interactions",
            json={"video_id": "abc12345678", "interaction_type": "rating"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

    def test_rating_out_of_range_rejected(self, client, auth_override):
        """Rating outside 1-5 should be rejected."""
        response = client.post(
            "/api/interactions",
            json={"video_id": "abc12345678", "interaction_type": "rating", "rating": 0},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/interactions",
            json={"video_id": "abc12345678", "interaction_type": "rating", "rating": 6},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

    def test_invalid_interaction_type_rejected(self, client, auth_override):
        """Unknown interaction type should be 422."""
        response = client.post(
            "/api/interactions",
            json={"video_id": "abc12345678", "interaction_type": "bookmark"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422

    def test_video_not_found_returns_404(self, client, auth_override):
        """Interaction for a nonexistent video returns 404."""
        db_override, _ = _make_async_db(fake_video=None, interaction_id=None)
        app.dependency_overrides[get_async_db] = db_override
        try:
            response = client.post(
                "/api/interactions",
                json={"video_id": "nonexistent", "interaction_type": "click"},
                headers={"Authorization": "Bearer fake-token"},
            )
        finally:
            app.dependency_overrides.pop(get_async_db, None)

        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    def test_invalid_video_id_format_rejected(self, client, auth_override):
        """Invalid YouTube ID format should be 422."""
        response = client.post(
            "/api/interactions",
            json={"video_id": "abc123", "interaction_type": "click"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 422
