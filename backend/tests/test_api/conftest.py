import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import get_current_user

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

@pytest.fixture
def auth_client() -> TestClient:
    # Build a fastapp test client with overridden dependencies
    app.dependency_overrides[get_current_user] = lambda: {"org_id": "test_org_id"}
    client = TestClient(app)
    yield client
    # Clean up overrides
    app.dependency_overrides.clear()
