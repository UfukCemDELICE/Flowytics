import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from backend.app.main import app
from backend.app.database import get_session
from backend.app.auth import verify_clerk_token
from backend.app.models.tenant import Tenant
from backend.app.utils import utc_now


@pytest.fixture
def gate_client():
    # Mock verify_clerk_token so authentication succeeds
    app.dependency_overrides[verify_clerk_token] = lambda: {"sub": "test_user_id", "org_id": "test_org_id"}
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_gate_active_trial_allowed(gate_client: TestClient):
    # Active trial: trial ends in the future
    mock_tenant = Tenant(
        id="t-active-001",
        clerk_org_id="test_org_id",
        name="Active Co",
        subscription_status="trial",
        trial_ends_at=utc_now() + timedelta(days=5)
    )
    
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = gate_client.get("/api/v1/me")
        assert resp.status_code == 200
        assert resp.json()["subscription_status"] == "trial"
    finally:
        del app.dependency_overrides[get_session]


def test_gate_expired_trial_blocked(gate_client: TestClient):
    # Expired trial
    mock_tenant = Tenant(
        id="t-expired-001",
        clerk_org_id="test_org_id",
        name="Expired Co",
        subscription_status="trial",
        trial_ends_at=utc_now() - timedelta(days=1)
    )
    
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = gate_client.get("/api/v1/me")
        assert resp.status_code == 402
        assert resp.json() == {"error": "trial_expired"}
    finally:
        del app.dependency_overrides[get_session]


def test_gate_inactive_blocked_canceled(gate_client: TestClient):
    # Canceled subscription
    mock_tenant = Tenant(
        id="t-canceled-001",
        clerk_org_id="test_org_id",
        name="Canceled Co",
        subscription_status="canceled"
    )
    
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = gate_client.get("/api/v1/me")
        assert resp.status_code == 402
        assert resp.json() == {"error": "subscription_inactive"}
    finally:
        del app.dependency_overrides[get_session]


def test_gate_inactive_blocked_past_due(gate_client: TestClient):
    # Past due subscription
    mock_tenant = Tenant(
        id="t-pastdue-001",
        clerk_org_id="test_org_id",
        name="Past Due Co",
        subscription_status="past_due"
    )
    
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = gate_client.get("/api/v1/me")
        assert resp.status_code == 402
        assert resp.json() == {"error": "subscription_inactive"}
    finally:
        del app.dependency_overrides[get_session]


def test_gate_exemption_allows_stripe(gate_client: TestClient):
    # Expired trial tenant should still be allowed to hit stripe endpoints
    mock_tenant = Tenant(
        id="t-exempt-001",
        clerk_org_id="test_org_id",
        name="Exempt Stripe Co",
        subscription_status="trial",
        trial_ends_at=utc_now() - timedelta(days=1),
        stripe_customer_id="cus_mock_123"
    )
    
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        # Patch create_portal_session call or internal stripe call to avoid actual Stripe API hit
        with patch("stripe.billing_portal.Session.create") as mock_portal_create:
            mock_portal_create.return_value = MagicMock(url="https://billing.stripe.com/mock")
            resp = gate_client.post("/api/v1/stripe/create-portal-session")
            # Should NOT return 402!
            assert resp.status_code == 200
            assert resp.json()["url"] == "https://billing.stripe.com/mock"
    finally:
        del app.dependency_overrides[get_session]


@pytest.mark.asyncio
async def test_slack_message_trial_expired():
    from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB
    from backend.app.services.slack_agent_runner import process_slack_message
    
    db = InMemoryDB()
    tenant = Tenant(
        id="t-expired-slack-001",
        clerk_org_id="expired_slack_org",
        name="Expired Slack Co",
        subscription_status="trial",
        trial_ends_at=utc_now() - timedelta(days=1),
        slack_team_id="T_EXPIRED_TEAM"
    )
    db.add(tenant)
    await db.commit()
    
    slack_event = {
        "team": "T_EXPIRED_TEAM",
        "user": "U_EXPIRED_USER",
        "channel": "C_EXPIRED_CHANNEL",
        "text": "What is my burn rate?",
        "ts": "12345.67"
    }
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch("backend.app.services.slack_agent_runner._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.slack_agent_runner.SlackClient") as MockSlackClient:
         
        mock_slack = MagicMock()
        mock_slack.send_reply = AsyncMock(return_value=True)
        MockSlackClient.return_value = mock_slack
        
        await process_slack_message(slack_event)
        
        # Verify reply was sent
        mock_slack.send_reply.assert_called_once()
        reply_args = mock_slack.send_reply.call_args
        reply_text = reply_args[1].get("text") or reply_args[0][2]
        assert "expired" in reply_text.lower()
        
        # Verify AgentRun was logged as failed with "trial_expired"
        agent_runs = db.store.get("agent_runs", [])
        assert len(agent_runs) == 1
        assert agent_runs[0].is_successful is False
        assert agent_runs[0].error_message == "trial_expired"
