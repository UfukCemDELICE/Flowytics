import pytest
from decimal import Decimal
from pydantic import BaseModel
from unittest.mock import patch, AsyncMock, MagicMock

from backend.app.utils import clean_unicode_minus, utc_now
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.app.models.agent_run import AgentRun
from backend.app.services.slack_agent_runner import process_slack_message
from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB

class MockModel(BaseModel):
    name: str
    amount_str: str
    items: list[str]

def test_clean_unicode_minus():
    # String
    assert clean_unicode_minus("−100.00") == "-100.00"
    # List
    assert clean_unicode_minus(["−100.00", "normal-hyphen", "hello"]) == ["-100.00", "normal-hyphen", "hello"]
    # Dict
    assert clean_unicode_minus({"val": "−100.00"}) == {"val": "-100.00"}
    # Pydantic model
    model = MockModel(name="−Name", amount_str="−50", items=["−item1", "−item2"])
    cleaned = clean_unicode_minus(model)
    assert cleaned.name == "-Name"
    assert cleaned.amount_str == "-50"
    assert cleaned.items == ["-item1", "-item2"]

@pytest.mark.asyncio
async def test_agent_run_failed_status_no_snapshots():
    db = InMemoryDB()

    tenant = Tenant(
        id="t-nosnap-test-01",
        clerk_org_id="nosnap_test_org",
        name="No Snap Test Co",
        subscription_status="active",
        slack_team_id="T_NOSNAP_TEST",
    )
    db.add(tenant)

    integration = Integration(
        id="int-nosnap-test-01",
        tenant_id="t-nosnap-test-01",
        provider="quickbooks",
        provider_connection_id="realm-nosnap-test",
        sync_status="active",
        last_synced_at=None,
    )
    db.add(integration)
    await db.commit()

    slack_event = {
        "team": "T_NOSNAP_TEST",
        "user": "U_USER",
        "channel": "C_CHANNEL",
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

        mock_slack = MagicMock()
        mock_slack.send_reply = AsyncMock(return_value="1711648000.000002")
        mock_slack.format_error_block = MagicMock(return_value=[])
        MockSlackClient.return_value = mock_slack

        await process_slack_message(slack_event)

        agent_runs = db.store.get("agent_runs", [])
        assert len(agent_runs) == 1
        assert agent_runs[0].is_successful is False
        assert agent_runs[0].status == "failed"

@pytest.mark.asyncio
async def test_outbound_slack_ts_captured():
    db = InMemoryDB()

    tenant = Tenant(
        id="t-outbound-test-01",
        clerk_org_id="outbound_test_org",
        name="Outbound Test Co",
        subscription_status="active",
        slack_team_id="T_OUTBOUND_TEST",
    )
    db.add(tenant)

    integration = Integration(
        id="int-outbound-test-01",
        tenant_id="t-outbound-test-01",
        provider="quickbooks",
        provider_connection_id="realm-outbound-test",
        sync_status="active",
        last_synced_at=utc_now(),
    )
    db.add(integration)
    await db.commit()

    # snapshots to bypass checks
    from backend.app.models.financial_snapshot import FinancialSnapshot
    from datetime import date
    pl_snap = FinancialSnapshot(
        tenant_id="t-outbound-test-01",
        snapshot_date=date.today(),
        source="quickbooks",
        data_type="profit_loss",
        raw_data={"Header": {"ReportName": "ProfitAndLoss"}, "Rows": {"Row": []}},
        period_start=date.today(),
        period_end=date.today()
    )
    bs_snap = FinancialSnapshot(
        tenant_id="t-outbound-test-01",
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

    slack_event = {
        "team": "T_OUTBOUND_TEST",
        "user": "U_USER",
        "channel": "C_CHANNEL",
        "text": "<@BOT> What is my burn rate?",
        "ts": "1711648000.000001",
        "thread_ts": "1711648000.000001",
    }

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    from langchain_core.messages import AIMessage
    mock_agent_result = {
        "messages": [AIMessage(content="CFO response: −$5,000 net burn.")],
        "recommended_model": "claude-haiku-4-5-20251001"
    }

    with patch("backend.app.services.slack_agent_runner._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.slack_agent_runner.agent_app.ainvoke", new_callable=AsyncMock) as mock_ainvoke, \
         patch("backend.app.services.slack_agent_runner.SlackClient") as MockSlackClient:

        mock_slack = MagicMock()
        mock_slack.send_reply = AsyncMock(return_value="1711648000.000002")
        mock_slack.format_cfo_response_block = MagicMock(return_value=[])
        MockSlackClient.return_value = mock_slack
        mock_ainvoke.return_value = mock_agent_result

        await process_slack_message(slack_event)

        slack_messages = db.store.get("slack_messages", [])
        outbound = [m for m in slack_messages if m.direction == "outbound"]
        assert len(outbound) == 1
        assert outbound[0].slack_ts == "1711648000.000002"
        # Ensure unicode minus is replaced by ASCII hyphen
        assert outbound[0].content == "CFO response: -$5,000 net burn."
