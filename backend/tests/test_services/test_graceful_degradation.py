import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app

def test_stripe_webhook_degradation():
    """Test Stripe webhook handles invoice.payment_failed gracefully."""
    client = TestClient(app)
    
    mock_event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "customer": "cus_12345"
            }
        }
    }
    
    with patch("backend.app.api.v1.stripe.verify_webhook", return_value=mock_event):
        # By not passing a mocked AsyncSession explicitly into app dependency, 
        # it might crash if the db isn't available, but we can patch sqlalchemy select or session
        # However, to be certain, we just mock the db execute method entirely inside stripe.py
        with patch("backend.app.api.v1.stripe.AsyncSession.execute", new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            # return None when finding tenant
            mock_result.scalar_one_or_none.return_value = None
            mock_execute.return_value = mock_result
            
            response = client.post(
                "/api/v1/stripe/webhook",
                json=mock_event, 
                headers={"stripe-signature": "dummy_sig"}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "success"

@pytest.mark.asyncio
async def test_proactive_alerts_no_data():
    """Test proactive alerts service gracefully loops past tenants with NO connected QuickBooks data."""
    from backend.app.services.proactive_alerts import run_proactive_alerts
    from backend.app.models.tenant import Tenant
    
    mock_tenant = Tenant(id=1, clerk_org_id="test_org", subscription_status="active", slack_team_id="team_123")
    
    mock_session = AsyncMock()
    # first execute is selecting tenants
    mock_result_tenants = MagicMock()
    mock_result_tenants.scalars().all.return_value = [mock_tenant]
    
    # subsequent executes are selecting P&L and BS which we want to simulate as missing
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None
    
    mock_session.execute.side_effect = [mock_result_tenants, mock_result_empty, mock_result_empty]
    
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

