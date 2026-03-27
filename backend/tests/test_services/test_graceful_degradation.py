import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app

def test_stripe_webhook_degradation():
    """Test Stripe webhook handles invoice.payment_failed gracefully."""
    from backend.app.database import get_session

    mock_event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "customer": "cus_12345"
            }
        }
    }

    # Create a mock async session that returns no tenant
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    async def override_get_session():
        yield mock_session

    # Override the FastAPI dependency instead of patching the class
    app.dependency_overrides[get_session] = override_get_session

    try:
        client = TestClient(app)
        with patch("backend.app.api.v1.stripe.verify_webhook", return_value=mock_event):
            response = client.post(
                "/api/v1/stripe/webhook",
                json=mock_event,
                headers={"stripe-signature": "dummy_sig"}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "success"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_proactive_alerts_no_data():
    """Test proactive alerts service gracefully loops past tenants with NO connected QuickBooks data."""
    from datetime import datetime, timezone
    from backend.app.services.proactive_alerts import run_proactive_alerts
    from backend.app.models.tenant import Tenant
    from backend.app.models.integration import Integration
    
    mock_tenant = Tenant(id=1, clerk_org_id="test_org", subscription_status="active", slack_team_id="team_123", name="Test")
    mock_integration = Integration(
        id="int-1", tenant_id="1", provider="quickbooks",
        provider_connection_id="realm-1", sync_status="active",
        last_synced_at=datetime.now(timezone.utc),
    )
    
    mock_session = AsyncMock()
    # first execute: selecting tenants
    mock_result_tenants = MagicMock()
    mock_result_tenants.scalars().all.return_value = [mock_tenant]
    
    # second execute: selecting Integration (freshness gate)
    mock_result_integration = MagicMock()
    mock_result_integration.scalar_one_or_none.return_value = mock_integration
    
    # third+fourth executes: P&L and BS snapshots (missing)
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None
    
    mock_session.execute.side_effect = [mock_result_tenants, mock_result_integration, mock_result_empty, mock_result_empty]
    
    # mock context manager behavior for session_factory
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session_factory.return_value.__aexit__.return_value = None

    with patch("backend.app.services.proactive_alerts._get_engine", return_value=(None, mock_session_factory)):
        try:
            await run_proactive_alerts()
            # If we reach here without exceptions, test passes
            assert True
        except Exception as e:
            pytest.fail(f"run_proactive_alerts crashed unexpectedly on missing data: {e}")

