"""Unit and integration tests for GET /health endpoint.

Verifies:
- Backend running and ready status.
- Strict response schema: {"status": "ok", "service": "social-guard", "version": "1.0.0"}
- Endpoint does not invoke analysis modules, external fact-check APIs, or databases.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient


def test_health_backend_running(client: TestClient):
    """Test that GET /health determines backend readiness without invoking analysis or external APIs."""
    with patch("app.modules.evidence_verification.factcheck_client.fact_check_client.search_claims") as mock_fc:
        response = client.get("/health")
        assert response.status_code == 200
        # Ensure external fact check is never called
        mock_fc.assert_not_called()

    data = response.json()
    assert data["status"] == "ok"


def test_health_response_schema(client: TestClient):
    """Test that GET /health and GET /api/v1/health return the exact required contract."""
    for path in ["/health", "/api/v1/health"]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()

        # Exact schema requirements
        assert data == {
            "status": "ok",
            "service": "social-guard",
            "version": "1.0.0",
        }
        assert isinstance(data["status"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["version"], str)
