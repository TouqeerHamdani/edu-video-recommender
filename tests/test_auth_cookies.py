"""
Tests for authentication cookie behavior in dev vs production.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def create_mock_auth_response():
    """Create a mock Supabase auth response."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.user_metadata = {}

    mock_session = MagicMock()
    mock_session.access_token = "fake-access-token"
    mock_session.refresh_token = "fake-refresh-token"

    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_response.session = mock_session

    return mock_response


class TestAuthCookies:
    """Tests for cookie security attributes in dev vs production."""

    def test_login_cookies_development(self, client):
        """
        Verify that in development, cookies are NOT Secure and SameSite=Lax.
        """
        mock_response = create_mock_auth_response()

        # Patch supabase at the client module level (where it's created)
        # AND patch ENV at auth module level
        with patch("backend.client.supabase") as mock_supabase, \
             patch("backend.auth.supabase") as mock_auth_supabase, \
             patch("backend.auth.ENV", "development"):
            
            mock_supabase.auth.sign_in_with_password.return_value = mock_response
            mock_auth_supabase.auth.sign_in_with_password.return_value = mock_response

            response = client.post("/api/login", json={
                "email": "test@example.com",
                "password": "password"
            })

        assert response.status_code == 200

        # Get list of all Set-Cookie headers
        set_cookie_headers = response.headers.get_list("set-cookie")

        # Development: SameSite=Lax should be present
        has_samesite_lax = any("samesite=lax" in header.lower() for header in set_cookie_headers)
        assert has_samesite_lax, f"No cookie with SameSite=Lax found in {set_cookie_headers}"

        # Development: Secure should NOT be present
        has_secure = any("; secure" in header.lower() for header in set_cookie_headers)
        assert not has_secure, f"Found Secure attribute in cookies (unexpected in dev): {set_cookie_headers}"

    def test_login_cookies_production(self, client):
        """
        Verify that in production, cookies ARE Secure and SameSite=None.
        """
        mock_response = create_mock_auth_response()

        with patch("backend.client.supabase") as mock_supabase, \
             patch("backend.auth.supabase") as mock_auth_supabase, \
             patch("backend.auth.ENV", "production"):
            
            mock_supabase.auth.sign_in_with_password.return_value = mock_response
            mock_auth_supabase.auth.sign_in_with_password.return_value = mock_response

            response = client.post("/api/login", json={
                "email": "test@example.com",
                "password": "password"
            })

        assert response.status_code == 200

        # Get list of all Set-Cookie headers
        set_cookie_headers = response.headers.get_list("set-cookie")
        combined_cookies = ", ".join(set_cookie_headers)

        # Production: Secure SHOULD be present
        assert "secure" in combined_cookies.lower(), f"Secure not found in {combined_cookies}"

        # Production: SameSite=None should be present
        assert "samesite=none" in combined_cookies.lower(), f"SameSite=None not found in {combined_cookies}"
