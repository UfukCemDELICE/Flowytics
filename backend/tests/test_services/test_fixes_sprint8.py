import pytest
import jwt
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.app.main import app
from backend.app.config import get_settings
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.models.slack_message import SlackUserMap, SlackMessage
from backend.app.auth import fetch_clerk_org_name, fetch_clerk_user_name, get_current_user


# --- FIX 1 Tests ---

@pytest.mark.asyncio
async def test_fetch_clerk_org_name():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"name": "Acme Org"}
        mock_get.return_value = mock_resp
        
        name = await fetch_clerk_org_name("org_123", "secret_key")
        assert name == "Acme Org"

@pytest.mark.asyncio
async def test_fetch_clerk_user_name():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"first_name": "John", "last_name": "Doe"}
        mock_get.return_value = mock_resp
        
        name = await fetch_clerk_user_name("user_123", "secret_key")
        assert name == "John Doe's Workspace"

@pytest.mark.asyncio
async def test_get_current_user_provisions_with_real_name():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # Tenant doesn't exist
    mock_session.execute.return_value = mock_res
    
    claims = {
        "org_id": "org_123",
        "sub": "user_123",
        "org_name": "Calculated Corp"
    }
    
    with patch("backend.app.auth.get_settings") as mock_settings:
        mock_sett = MagicMock()
        mock_sett.CLERK_SECRET_KEY = "test_clerk_secret"
        mock_settings.return_value = mock_sett
        
        result = await get_current_user(claims, mock_session)
        assert result["org_id"] == "org_123"
        assert result["user_id"] == "user_123"
        
        # Verify Tenant added has the real name
        mock_session.add.assert_called_once()
        added_tenant = mock_session.add.call_args[0][0]
        assert isinstance(added_tenant, Tenant)
        assert added_tenant.name == "Calculated Corp"
        mock_session.commit.assert_called_once()


# --- FIX 2 Tests ---

def test_slack_oauth_redirect_saves_channel_and_maps_user():
    settings = get_settings()
    client = TestClient(app)
    
    # 1. Mock Database
    mock_tenant = Tenant(
        id="88888888-8888-8888-8888-888888888888",
        clerk_org_id="org_test_v2",
        name="Personal or Development Tenant"
    )
    
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_res_tenant = MagicMock()
    mock_res_tenant.scalar_one_or_none.side_effect = [
        mock_tenant,  # For select(Tenant)
        None          # For select(SlackUserMap)
    ]
    mock_session.execute.return_value = mock_res_tenant
    
    # Override get_session dependency
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    
    # 2. Mock Slack Web Client
    mock_slack_response = {
        "ok": True,
        "team": {"id": "T_MOCK_123"},
        "authed_user": {"id": "U_MOCK_AUTHED"},
        "incoming_webhook": {
            "channel_id": "C_MOCK_WEBHOOK_123"
        }
    }
    
    state_payload = {"org_id": "org_test_v2", "clerk_user_id": "user_clerk_123"}
    state_token = jwt.encode(state_payload, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")
    
    with patch("backend.app.api.v1.slack.AsyncWebClient.oauth_v2_access", new_callable=AsyncMock) as mock_oauth, \
         patch("backend.app.api.v1.slack.asyncio.create_task") as mock_create_task:
        mock_oauth.return_value = mock_slack_response
        
        resp = client.get(f"/api/v1/slack/oauth_redirect?code=mock_code&state={state_token}", follow_redirects=False)
        assert resp.status_code == 307
        
        # Verify Slack channel ID and Slack team ID are updated
        assert mock_tenant.slack_team_id == "T_MOCK_123"
        assert mock_tenant.slack_channel_id == "C_MOCK_WEBHOOK_123"
        
        # Verify SlackUserMap was added
        added_objs = [call_args[0][0] for call_args in mock_session.add.call_args_list]
        slack_user_maps = [obj for obj in added_objs if isinstance(obj, SlackUserMap)]
        assert len(slack_user_maps) == 1
        assert slack_user_maps[0].slack_user_id == "U_MOCK_AUTHED"
        assert slack_user_maps[0].clerk_user_id == "user_clerk_123"
        assert slack_user_maps[0].tenant_id == mock_tenant.id

    del app.dependency_overrides[get_session]


# --- FIX 3 Tests ---

@pytest.mark.asyncio
async def test_stripe_webhook_checkout_session_completed_trial_dates():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_tenant = Tenant(
        id="99999999-9999-9999-9999-999999999999",
        clerk_org_id="org_stripe_test",
        name="Stripe Test Corp"
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    # Event mock payload
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"clerk_org_id": "org_stripe_test"},
                "customer": "cus_12345",
                "subscription": "sub_12345"
            }
        }
    }
    
    # Mock stripe subscription retrieve
    mock_sub = {
        "trial_start": 1700000000,
        "trial_end": 1701000000
    }
    
    with patch("stripe.Webhook.construct_event", return_value=event), \
         patch("stripe.Subscription.retrieve", return_value=mock_sub):
        
        client = TestClient(app)
        
        # Override get_session
        async def override_get_session():
            yield mock_session
        app.dependency_overrides[get_session] = override_get_session
        
        headers = {"stripe-signature": "t=1,v1=1"}
        resp = client.post("/api/v1/stripe/webhook", json=event, headers=headers)
        assert resp.status_code == 200
        
        # Assert trial dates updated
        assert mock_tenant.trial_started_at == datetime.utcfromtimestamp(1700000000)
        assert mock_tenant.trial_ends_at == datetime.utcfromtimestamp(1701000000)
        assert mock_tenant.stripe_customer_id == "cus_12345"
        assert mock_tenant.stripe_subscription_id == "sub_12345"
        
        del app.dependency_overrides[get_session]

@pytest.mark.asyncio
async def test_stripe_webhook_customer_subscription_updated_trial_dates():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_tenant = Tenant(
        id="99999999-9999-9999-9999-999999999999",
        clerk_org_id="org_stripe_test",
        stripe_customer_id="cus_12345",
        name="Stripe Test Corp"
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_res
    
    # Event mock payload
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "customer": "cus_12345",
                "status": "active",
                "trial_start": 1702000000,
                "trial_end": 1703000000
            }
        }
    }
    
    with patch("stripe.Webhook.construct_event", return_value=event):
        client = TestClient(app)
        
        # Override get_session
        async def override_get_session():
            yield mock_session
        app.dependency_overrides[get_session] = override_get_session
        
        headers = {"stripe-signature": "t=1,v1=1"}
        resp = client.post("/api/v1/stripe/webhook", json=event, headers=headers)
        assert resp.status_code == 200
        
        # Assert trial dates updated directly from the event data object
        assert mock_tenant.trial_started_at == datetime.utcfromtimestamp(1702000000)
        assert mock_tenant.trial_ends_at == datetime.utcfromtimestamp(1703000000)
        
        del app.dependency_overrides[get_session]


# --- FIX 4 Tests ---

@pytest.mark.asyncio
async def test_process_slack_message_maps_clerk_user_id_by_email():
    from backend.app.services.slack_agent_runner import process_slack_message
    from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB
    
    db = InMemoryDB()
    tenant = Tenant(
        id="t-sprint8-001",
        clerk_org_id="sprint8_org",
        name="Sprint 8 Corp",
        slack_team_id="T_SPRINT8"
    )
    db.add(tenant)
    await db.commit()
    
    slack_event = {
        "team": "T_SPRINT8",
        "user": "U_SPRINT8_USER",
        "channel": "C_SPRINT8_CHANNEL",
        "text": "hello CFO",
        "ts": "180000.01"
    }
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock Slack users.info
    mock_slack_client = MagicMock()
    mock_slack_client.send_reply = AsyncMock()
    mock_slack_client.format_error_block = MagicMock(return_value=[])
    mock_slack_client.client.users_info = AsyncMock(return_value={
        "ok": True,
        "user": {
            "profile": {
                "email": "user@sprint8.com"
            }
        }
    })
    
    # Mock Clerk users API
    mock_clerk_resp = MagicMock()
    mock_clerk_resp.status_code = 200
    mock_clerk_resp.json.return_value = [{"id": "user_clerk_sprint8"}]
    
    with patch("backend.app.services.slack_agent_runner._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.slack_agent_runner.SlackClient", return_value=mock_slack_client), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
         
        mock_get.return_value = mock_clerk_resp
        
        # We also mock agent run execution to stop it early or let it fail cleanly
        # since we are only testing SlackUserMap creation here. We'll raise an exception
        # after DB commit is done.
        with patch("backend.app.services.slack_agent_runner.parse_financial_summary") as mock_parse:
            # force an exception in parsing to prevent agent run execution (which we don't care about here)
            mock_parse.side_effect = Exception("Stop execution")
            
            await process_slack_message(slack_event)
            
            # Check user map table
            slack_user_maps = db.store.get("slack_user_map", [])
            assert len(slack_user_maps) == 1
            assert slack_user_maps[0].slack_user_id == "U_SPRINT8_USER"
            assert slack_user_maps[0].clerk_user_id == "user_clerk_sprint8"
            assert slack_user_maps[0].tenant_id == tenant.id


@pytest.mark.asyncio
async def test_process_slack_message_saves_output_result():
    from backend.app.services.slack_agent_runner import process_slack_message
    from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB
    from langchain_core.messages import AIMessage, ToolMessage
    from backend.app.models.financial_snapshot import FinancialSnapshot
    from backend.app.models.integration import Integration

    db = InMemoryDB()
    tenant = Tenant(
        id="t-sprint8-002",
        clerk_org_id="sprint8_org2",
        name="Sprint 8 Corp 2",
        slack_team_id="T_SPRINT8"
    )
    db.add(tenant)
    
    integration = Integration(
        tenant_id="t-sprint8-002",
        provider="quickbooks",
        sync_status="active",
        last_synced_at=datetime.now(timezone.utc)
    )
    db.add(integration)

    pl_snap = FinancialSnapshot(
        tenant_id="t-sprint8-002",
        data_type="profit_loss",
        snapshot_date=datetime.now(timezone.utc).date(),
        source="quickbooks",
        raw_data={"Header": {"ReportName": "ProfitAndLoss"}, "Rows": {"Row": []}}
    )
    bs_snap = FinancialSnapshot(
        tenant_id="t-sprint8-002",
        data_type="balance_sheet",
        snapshot_date=datetime.now(timezone.utc).date(),
        source="quickbooks",
        raw_data={"Header": {"ReportName": "BalanceSheet"}, "Rows": {"Row": []}}
    )
    db.add(pl_snap)
    db.add(bs_snap)
    await db.commit()

    slack_event = {
        "team": "T_SPRINT8",
        "user": "U_SPRINT8_USER",
        "channel": "C_SPRINT8_CHANNEL",
        "text": "hello CFO",
        "ts": "180000.02"
    }

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_slack_client = MagicMock()
    mock_slack_client.send_reply = AsyncMock()
    mock_slack_client.format_cfo_response_block = MagicMock(return_value=[])

    # AI calls tool and tool returns some structured JSON
    ai_msg = AIMessage(content="", tool_calls=[{"name": "calculate_burn_rate", "args": {}, "id": "call_br"}])
    tool_msg = ToolMessage(content='{"net_burn_monthly": "15000.00", "gross_burn_monthly": "20000.00", "burn_multiple": "1.5", "trend": "stable", "trend_slope": "0", "period_months": 3}', name="calculate_burn_rate", tool_call_id="call_br")
    final_ai_msg = AIMessage(content="Your net burn is $15,000.")

    mock_agent_result = {
        "messages": [ai_msg, tool_msg, final_ai_msg]
    }

    with patch("backend.app.services.slack_agent_runner._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.slack_agent_runner.SlackClient", return_value=mock_slack_client), \
         patch("backend.app.services.slack_agent_runner.agent_app") as mock_agent, \
         patch("backend.app.services.slack_agent_runner.parse_financial_summary") as mock_parse:
         
        mock_agent.ainvoke = AsyncMock(return_value=mock_agent_result)
        mock_parse.return_value = MagicMock()

        await process_slack_message(slack_event)

        # Check agent runs table
        agent_runs = db.store.get("agent_runs", [])
        assert len(agent_runs) == 1
        run = agent_runs[0]
        assert run.is_successful is True
        assert run.status == "completed"
        # Verify output_result matches the parsed tool message content
        assert run.output_result is not None
        assert "calculate_burn_rate" in run.output_result
        assert run.output_result["calculate_burn_rate"]["net_burn_monthly"] == "15000.00"
        assert run.output_result["calculate_burn_rate"]["burn_multiple"] == "1.5"
