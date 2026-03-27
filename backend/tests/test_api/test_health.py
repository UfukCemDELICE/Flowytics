from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Health check endpoint should return 200 without auth."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
