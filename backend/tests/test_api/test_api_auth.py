from fastapi.testclient import TestClient

def test_protected_route_without_auth(client: TestClient):
    """Test that auth endpoints require a valid clerk JWT header."""
    response = client.get("/api/v1/me")
    # Our dependency injects auth, typically failing down into a 401 unauthenticated
    # By default, FastAPI might return 401 if missing Authorization header
    # Clerk handles this. It should definitely NOT return 200.
    assert response.status_code == 401

def test_protected_route_with_auth(auth_client: TestClient):
    """Test that auth endpoints succeed when mocking the get_current_user dependency."""
    response = auth_client.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json()["org_id"] == "test_org_id"

def test_quickbooks_oauth_redirect_without_auth(client: TestClient):
    """Test that Quickbooks integration auth requires valid auth."""
    response = client.get("/api/v1/quickbooks/auth")
    assert response.status_code == 401

from unittest.mock import patch

def test_quickbooks_oauth_redirect_with_auth(auth_client: TestClient):
    """Test that Quickbooks integration returns an Auth URL for valid clients."""
    with patch("backend.app.api.v1.quickbooks.quickbooks.generate_auth_url", return_value="https://appcenter.intuit.com/connect/oauth2?mock=true"):
        response = auth_client.get("/api/v1/quickbooks/auth")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "appcenter.intuit.com/connect/oauth2" in data["auth_url"]
