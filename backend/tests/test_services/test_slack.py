import pytest
from backend.app.integrations.slack import SlackClient

def test_slack_client_block_formatting():
    client = SlackClient()
    
    # Test CFO Response Block (header + section + divider + context)
    text = "Runway is 5 months."
    cfo_blocks = client.format_cfo_response_block(text)
    
    assert len(cfo_blocks) == 4
    assert cfo_blocks[0]["type"] == "header"
    assert "AI CFO" in cfo_blocks[0]["text"]["text"]
    assert cfo_blocks[1]["type"] == "section"
    assert "Runway is 5 months" in cfo_blocks[1]["text"]["text"]
    assert cfo_blocks[-1]["type"] == "context"
    
    # Test Proactive Alert Block (header + divider + body + divider + CTA + context)
    alert_text = "Burn rate spiked by 30%."
    alert_blocks = client.format_proactive_alert_block(alert_text, severity="critical")
    
    assert len(alert_blocks) == 6
    assert alert_blocks[0]["type"] == "header"
    assert "🚨" in alert_blocks[0]["text"]["text"]
    assert "CRITICAL" in alert_blocks[0]["text"]["text"]
    # Alert text is in the body section
    body_section = alert_blocks[2]
    assert "Burn rate spiked" in body_section["text"]["text"]

def test_slack_agent_runner_import():
    # If this fails, we have an import cycle or syntax error in our agent runner
    try:
        from backend.app.services.slack_agent_runner import process_slack_message
        assert callable(process_slack_message)
    except Exception as e:
        pytest.fail(f"slack_agent_runner import failed: {e}")

def test_proactive_alerts_import():
    # If this fails, we have an import cycle or syntax error in our proactive alerts
    try:
        from backend.app.services.proactive_alerts import run_proactive_alerts
        assert callable(run_proactive_alerts)
    except Exception as e:
        pytest.fail(f"proactive_alerts import failed: {e}")

@pytest.mark.asyncio
async def test_slack_agent_run_logging():
    import asyncio
    from unittest.mock import patch, AsyncMock, MagicMock
    from datetime import datetime, timezone, date
    from decimal import Decimal

    from backend.app.models.tenant import Tenant
    from backend.app.models.integration import Integration
    from backend.app.models.financial_snapshot import FinancialSnapshot
    from backend.app.services.slack_agent_runner import process_slack_message
    from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB

    db = InMemoryDB()

    # 1. Setup mock tenant
    tenant = Tenant(
        id="t-logging-001",
        clerk_org_id="logging_org",
        name="Logging Co",
        subscription_status="active",
        slack_team_id="T_LOGGING_TEAM",
    )
    db.add(tenant)

    # 2. Setup QuickBooks integration and snapshot (so data freshness checks pass)
    integration = Integration(
        id="int-logging-001",
        tenant_id="t-logging-001",
        provider="quickbooks",
        provider_connection_id="realm-logging",
        sa_column=None,
        sync_status="active",
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(integration)

    pl_snap = FinancialSnapshot(
        tenant_id="t-logging-001",
        snapshot_date=date.today(),
        source="quickbooks",
        data_type="profit_loss",
        raw_data={"Header": {"ReportName": "ProfitAndLoss"}, "Rows": {"Row": []}},
        period_start=date.today(),
        period_end=date.today()
    )
    bs_snap = FinancialSnapshot(
        tenant_id="t-logging-001",
        snapshot_date=date.today(),
        source="quickbooks",
        data_type="balance_sheet",
        raw_data={"Header": {"ReportName": "BalanceSheet"}, "Rows": {"Row": []}},
        period_start=date.today(),
        period_end=date.today()
    )
    db.add(pl_snap)
    db.add(bs_snap)

    await db.commit()

    # 3. Define mock Agent result
    # We need a message with tool_calls
    from langchain_core.messages import AIMessage
    mock_msg = AIMessage(
        content="Here is the burn rate details.",
        tool_calls=[
            {"name": "calculate_burn_rate", "args": {}, "id": "tc-1"},
            {"name": "calculate_runway", "args": {}, "id": "tc-2"}
        ]
    )
    
    mock_agent_result = {
        "messages": [mock_msg],
        "recommended_model": "claude-haiku-4-5-20251001"
    }

    slack_event = {
        "team": "T_LOGGING_TEAM",
        "user": "U_LOGGING_USER",
        "channel": "C_LOGGING_CHANNEL",
        "text": "<@BOT> What is my burn rate?",
        "ts": "1711648000.000001",
        "thread_ts": "1711648000.000001",
    }

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.services.slack_agent_runner._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.slack_agent_runner.agent_app.ainvoke", new_callable=AsyncMock) as mock_ainvoke, \
         patch("backend.app.services.slack_agent_runner.SlackClient") as MockSlackClient:

        async def slow_invoke(inputs):
            await asyncio.sleep(0.005) # sleep for 5ms to ensure duration_ms > 0
            return mock_agent_result

        mock_ainvoke.side_effect = slow_invoke

        # Mock Slack response formatting
        mock_slack = MagicMock()
        mock_slack.send_reply = AsyncMock(return_value=True)
        MockSlackClient.return_value = mock_slack

        await process_slack_message(slack_event)

    # 4. Assertions on AgentRun table
    agent_runs = db.store.get("agent_runs", [])
    assert len(agent_runs) == 1
    run = agent_runs[0]

    assert run.is_successful is True
    assert run.status == "completed"
    assert run.tools_called == ["calculate_burn_rate", "calculate_runway"]
    assert run.model_used == "claude-haiku-4-5-20251001"
    assert isinstance(run.duration_ms, int)
    assert run.duration_ms > 0
