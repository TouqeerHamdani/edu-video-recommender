"""
Tests for /api/health endpoint.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client):
        """GET /api/health should return 200 OK."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_correct_structure(self, client):
        """Health response should contain expected fields."""
        response = client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "message" in data
        assert "database" in data
        assert "orm" in data
        assert "environment" in data

    def test_health_database_connected(self, client):
        """Health should report database as connected when DB is up."""
        response = client.get("/api/health")
        data = response.json()

        # If we get 200, database should be connected
        assert data["status"] == "ok"
        assert "connected" in data["database"]

    @patch("backend.app.test_connection")
    def test_health_database_disconnected(self, mock_test_conn, client):
        """Health should report error when database is down."""
        mock_test_conn.return_value = (False, "Connection refused")

        response = client.get("/api/health")
        data = response.json()

        assert data["status"] == "error"
        assert "disconnected" in data["database"]


class TestRootEndpoint:
    """Tests for the root endpoint (serves homepage HTML)."""

    def test_root_returns_200(self, client):
        """GET / should return 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_html(self, client):
        """Root should return HTML content (project.html)."""
        response = client.get("/")
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type

