"""Unit and integration tests for /health endpoint."""

from fastapi.testclient import TestClient


def test_health_check_returns_200(client: TestClient):
    """Test that GET /health returns 200 and standard health check schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "social-guard"
    assert "version" in data
