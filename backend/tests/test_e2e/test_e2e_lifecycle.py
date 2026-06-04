"""
End-to-end integration test: Signup → Connect QBO → Sync → Connect Slack → Welcome → Slack Report

This test simulates the complete onboarding and first-use lifecycle of a Flowytics customer.
External services (QuickBooks API, Slack API, Anthropic Claude) are mocked at their boundary,
while all internal service wiring is tested with real logic.

Phases:
  1. SIGNUP:    Stripe webhook creates Tenant with active subscription
  2. QBO CONNECT: OAuth callback saves encrypted tokens + Integration row
  3. DATA SYNC:   sync_tenant pulls P&L/BS/CF, saves FinancialSnapshots
  4. SLACK CONNECT: Slack OAuth maps team_id to tenant
  5. WELCOME:      Both milestones met → welcome message sent to #general
  6. SLACK REPORT:  User @mentions bot → agent invoked → CFO response returned
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration


# ────────────────────────────────────────────────────────────────
#  Shared test fixtures
# ────────────────────────────────────────────────────────────────

E2E_ORG_ID = "e2e_org_001"
E2E_REALM_ID = "e2e_realm_qbo"
E2E_TEAM_ID = "T_E2E_TEAM"

# Realistic QBO report stubs
STUB_PROFIT_LOSS = {
    "Header": {"ReportName": "ProfitAndLoss"},
    "Rows": {"Row": [
        {"Summary": {"ColData": [{"value": "Total Income"}, {"value": "50000.00"}]}},
        {"Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "35000.00"}]}},
        {"Summary": {"ColData": [{"value": "Net Income"}, {"value": "15000.00"}]}},
    ]},
}

STUB_BALANCE_SHEET = {
    "Header": {"ReportName": "BalanceSheet"},
    "Rows": {"Row": [
        {"Summary": {"ColData": [{"value": "Total Assets"}, {"value": "120000.00"}]}},
        {"Summary": {"ColData": [{"value": "Total Liabilities"}, {"value": "30000.00"}]}},
        {"Summary": {"ColData": [{"value": "Total Equity"}, {"value": "90000.00"}]}},
    ]},
}

STUB_CASH_FLOW = {
    "Header": {"ReportName": "CashFlow"},
    "Rows": {"Row": [
        {"Summary": {"ColData": [{"value": "Net Cash from Operations"}, {"value": "18000.00"}]}},
    ]},
}


class InMemoryDB:
    """
    Lightweight in-memory store that mimics async SQLAlchemy session behavior.
    Stores model instances keyed by (table_name, id) and supports filtered queries.
    """

    def __init__(self):
        self.store: dict[str, list] = {}  # table_name -> [model_instances]
        self._pending: list = []

    def add(self, obj):
        self._pending.append(obj)

    async def commit(self):
        for obj in self._pending:
            table = getattr(obj, "__tablename__", obj.__class__.__name__)
            if table not in self.store:
                self.store[table] = []
            # Update-or-insert by id
            existing = next((o for o in self.store[table] if o.id == obj.id), None)
            if existing:
                idx = self.store[table].index(existing)
                self.store[table][idx] = obj
            else:
                self.store[table].append(obj)
        self._pending.clear()

    async def refresh(self, obj):
        pass  # No-op in memory

    async def execute(self, stmt):
        """
        Naive query execution: inspects SQLModel select() to find the target
        table and applies where-clause comparisons by attribute matching.
        """
        return InMemoryResult(self._execute_sync(stmt))

    def _execute_sync(self, stmt):
        """Parse the compiled statement to match stored objects."""
        # Get the entity being queried
        entity = None
        if hasattr(stmt, "column_descriptions"):
            entity = stmt.column_descriptions[0].get("entity")
        if entity is None:
            return None

        table_name = getattr(entity, "__tablename__", entity.__name__)
        candidates = self.store.get(table_name, [])

        # Extract where clause comparisons
        if hasattr(stmt, "whereclause") and stmt.whereclause is not None:
            results = self._filter_candidates(candidates, stmt.whereclause)
        else:
            results = list(candidates)

        return results[0] if results else None

    def _filter_candidates(self, candidates, clause):
        """Recursively filter candidates against SQLAlchemy BooleanClause."""
        clause_str = str(clause)

        # Handle AND conjunctions (BooleanClauseList)
        if hasattr(clause, "clauses") and "AND" in clause_str.upper():
            results = list(candidates)
            for sub in clause.clauses:
                results = self._filter_candidates(results, sub)
            return results

        # Handle OR disjunctions
        if hasattr(clause, "clauses") and "OR" in clause_str.upper():
            combined = []
            for sub in clause.clauses:
                combined.extend(self._filter_candidates(candidates, sub))
            # Deduplicate while preserving order
            seen = set()
            return [x for x in combined if id(x) not in seen and not seen.add(id(x))]

        # Handle IN clauses (e.g., sync_status IN ('active', 'error'))
        if "IN" in clause_str.upper() and hasattr(clause, "left"):
            col_name = str(clause.left).split(".")[-1]
            # Extract bound values from the IN clause
            if hasattr(clause, "right") and hasattr(clause.right, "clauses"):
                values = []
                for v in clause.right.clauses:
                    if hasattr(v, "effective_value"):
                        values.append(v.effective_value)
                    elif hasattr(v, "value"):
                        values.append(v.value)
                return [c for c in candidates if getattr(c, col_name, None) in values]
            return list(candidates)

        # Handle IS NOT NULL
        if "IS NOT NULL" in clause_str.upper():
            col_name = clause_str.split(".")[1].split(" ")[0] if "." in clause_str else None
            if col_name:
                return [c for c in candidates if getattr(c, col_name, None) is not None]
            return list(candidates)

        # Handle simple column == value comparisons
        if hasattr(clause, "left") and hasattr(clause, "right"):
            col_name = str(clause.left).split(".")[-1]
            if hasattr(clause.right, "effective_value"):
                value = clause.right.effective_value
                return [c for c in candidates if getattr(c, col_name, None) == value]
            elif hasattr(clause.right, "value"):
                value = clause.right.value
                return [c for c in candidates if getattr(c, col_name, None) == value]

        return list(candidates)


class InMemoryResult:
    """Mimics SQLAlchemy result proxy."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [self._value] if self._value else []


# ────────────────────────────────────────────────────────────────
#  E2E test
# ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_signup_connect_sync_slack_report():
    """
    Full lifecycle integration test:
    Signup → QBO Connect → Data Sync → Slack Connect → Welcome → Slack CFO Query
    """
    db = InMemoryDB()

    # ━━━━━ PHASE 1: SIGNUP (Stripe checkout.session.completed webhook) ━━━━━

    tenant = Tenant(
        id="t-e2e-001",
        clerk_org_id=E2E_ORG_ID,
        name="E2E Startup Inc",
        subscription_status="active",
        stripe_customer_id="cus_e2e_001",
        stripe_subscription_id="sub_e2e_001",
    )
    db.add(tenant)
    await db.commit()

    # Verify: Tenant exists in DB
    assert len(db.store.get("tenants", [])) == 1
    assert db.store["tenants"][0].subscription_status == "active"
    assert db.store["tenants"][0].name == "E2E Startup Inc"

    # ━━━━━ PHASE 2: QBO CONNECT (OAuth callback saves tokens) ━━━━━

    from backend.app.integrations.quickbooks import handle_callback

    # Mock the Intuit OAuth exchange
    with patch("backend.app.integrations.quickbooks.get_auth_client") as mock_auth:
        mock_client = MagicMock()
        mock_client.access_token = "e2e_access_token"
        mock_client.refresh_token = "e2e_refresh_token"
        mock_client.expires_in = 3600
        mock_client.x_refresh_token_expires_in = 8726400
        mock_auth.return_value = mock_client

        with patch("backend.app.integrations.quickbooks.get_fernet") as mock_fernet:
            mock_f = MagicMock()
            mock_f.encrypt.return_value = b"encrypted_tokens_stub"
            mock_fernet.return_value = mock_f

            integration = await handle_callback(
                code="e2e_auth_code",
                realm_id=E2E_REALM_ID,
                tenant_id="t-e2e-001",
                session=db,
            )

    # Verify: Integration created and active
    assert integration.provider == "quickbooks"
    assert integration.provider_connection_id == E2E_REALM_ID
    assert integration.sync_status == "active"
    assert integration.tenant_id == "t-e2e-001"
    assert len(db.store.get("integrations", [])) == 1

    # ━━━━━ PHASE 3: DATA SYNC (Pull QBO reports → save snapshots) ━━━━━

    from backend.app.services.sync import sync_tenant

    with patch("backend.app.services.sync.get_profit_and_loss", new_callable=AsyncMock) as mock_pl, \
         patch("backend.app.services.sync.get_balance_sheet", new_callable=AsyncMock) as mock_bs, \
         patch("backend.app.services.sync.get_cash_flow", new_callable=AsyncMock) as mock_cf:

        mock_pl.return_value = STUB_PROFIT_LOSS
        mock_bs.return_value = STUB_BALANCE_SHEET
        mock_cf.return_value = STUB_CASH_FLOW

        sync_result = await sync_tenant("t-e2e-001", db)

    # Verify: 3 snapshots created
    assert sync_result["status"] == "synced"
    assert sync_result["snapshots_created"] == 3

    snapshots = db.store.get("financial_snapshots", [])
    assert len(snapshots) == 3

    data_types = {s.data_type for s in snapshots}
    assert data_types == {"profit_loss", "balance_sheet", "cash_flow"}

    # Verify: each snapshot has correct raw data
    pl_snap = next(s for s in snapshots if s.data_type == "profit_loss")
    assert pl_snap.raw_data["Header"]["ReportName"] == "ProfitAndLoss"
    assert pl_snap.tenant_id == "t-e2e-001"
    assert pl_snap.source == "quickbooks"

    # Verify: integration updated with last_synced_at
    stored_integration = db.store["integrations"][0]
    assert stored_integration.last_synced_at is not None
    assert stored_integration.sync_status == "active"

    # ━━━━━ PHASE 4: SLACK CONNECT (OAuth maps team_id to tenant) ━━━━━

    tenant.slack_team_id = E2E_TEAM_ID
    db.add(tenant)
    await db.commit()

    # Verify: Tenant now has Slack mapped
    stored_tenant = db.store["tenants"][0]
    assert stored_tenant.slack_team_id == E2E_TEAM_ID

    # ━━━━━ PHASE 5: WELCOME MESSAGE (Both milestones met → fires) ━━━━━

    from backend.app.services.onboarding_welcome import _check_and_send

    with patch("backend.app.services.onboarding_welcome.SlackClient") as MockSlack:
        mock_slack_inst = MagicMock()
        mock_slack_inst.send_message = AsyncMock(return_value=True)
        MockSlack.return_value = mock_slack_inst

        welcome_sent = await _check_and_send("t-e2e-001", db)

    # Verify: Welcome was sent
    assert welcome_sent is True
    mock_slack_inst.send_message.assert_awaited_once()

    # Verify: onboarding_completed is True (prevents duplicate sends)
    assert db.store["tenants"][0].onboarding_completed is True

    # Verify: Welcome message contains key information
    call_args = mock_slack_inst.send_message.call_args
    welcome_text = call_args[0][1]  # fallback text
    welcome_blocks = call_args[1]["blocks"]
    assert "connected" in welcome_text.lower() or "✅" in welcome_text
    assert any("QuickBooks" in str(b) for b in welcome_blocks)
    assert any("burn rate" in str(b).lower() for b in welcome_blocks)

    # Verify: Second call is idempotent (no duplicate)
    with patch("backend.app.services.onboarding_welcome.SlackClient") as MockSlack2:
        mock_slack_inst2 = MagicMock()
        mock_slack_inst2.send_message = AsyncMock(return_value=True)
        MockSlack2.return_value = mock_slack_inst2

        welcome_sent_again = await _check_and_send("t-e2e-001", db)

    assert welcome_sent_again is False  # Already sent
    mock_slack_inst2.send_message.assert_not_awaited()

    # ━━━━━ PHASE 6: SLACK CFO QUERY (User asks → agent responds) ━━━━━

    from backend.app.services.slack_agent_runner import process_slack_message

    slack_event = {
        "team": E2E_TEAM_ID,
        "user": "U_E2E_USER",
        "channel": "C_E2E_CHANNEL",
        "text": "<@UBOTID> What is my burn rate?",
        "ts": "1711648000.000001",
        "thread_ts": "1711648000.000001",
    }

    # Mock: _get_engine returns a session factory that yields our in-memory DB
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # Mock: LangGraph agent returns a CFO response
    mock_agent_result = {
        "messages": [
            MagicMock(content="Based on your QuickBooks data, your current net burn rate is **$15,000/month**. "
                              "With $120,000 in total assets, this gives you approximately **8 months of runway**.")
        ]
    }

    with patch("backend.app.services.slack_agent_runner._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.slack_agent_runner.agent_app") as mock_agent, \
         patch("backend.app.services.slack_agent_runner.SlackClient") as MockSlackCFO:

        # Agent returns our stub
        mock_agent.ainvoke = AsyncMock(return_value=mock_agent_result)

        # Slack client captures the response
        mock_cfo_slack = MagicMock()
        mock_cfo_slack.send_reply = AsyncMock(return_value=True)
        mock_cfo_slack.format_cfo_response_block = MagicMock(return_value=[{"type": "section", "text": {"type": "mrkdwn", "text": "stub"}}])
        MockSlackCFO.return_value = mock_cfo_slack

        await process_slack_message(slack_event)

    # Verify: Agent was called with the cleaned user question
    mock_agent.ainvoke.assert_awaited_once()
    agent_input = mock_agent.ainvoke.call_args[0][0]
    assert agent_input["messages"][0][1] == "What is my burn rate?"

    # Verify: Slack reply was sent back
    mock_cfo_slack.send_reply.assert_awaited()
    reply_args = mock_cfo_slack.send_reply.call_args
    reply_channel = reply_args[0][0]
    reply_text = reply_args[1].get("text") or reply_args[0][2]
    assert reply_channel == "C_E2E_CHANNEL"
    assert "burn rate" in reply_text.lower() or "$15,000" in reply_text

    # Verify: Agent run was logged in DB
    agent_runs = db.store.get("agent_runs", [])
    assert len(agent_runs) == 1
    assert agent_runs[0].tenant_id == "t-e2e-001"
    assert agent_runs[0].trigger_type == "slack_message"

    # Verify: Slack messages were logged (1 inbound + 1 outbound)
    slack_msgs = db.store.get("slack_messages", [])
    assert len(slack_msgs) == 2
    directions = {m.direction for m in slack_msgs}
    assert directions == {"inbound", "outbound"}


# ────────────────────────────────────────────────────────────────
#  Error path E2E: Token expired mid-flow
# ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_token_expired_during_sync():
    """
    Tests the error recovery path: QBO tokens expire during sync →
    integration marked disconnected → Slack agent blocks with CTA.
    """
    db = InMemoryDB()

    # Setup: tenant + active integration
    tenant = Tenant(
        id="t-err-001",
        clerk_org_id="err_org",
        name="Error Path Co",
        subscription_status="active",
        slack_team_id="T_ERR",
    )
    integration = Integration(
        id="int-err-001",
        tenant_id="t-err-001",
        provider="quickbooks",
        provider_connection_id="realm-err",
        sync_status="active",
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    db.add(integration)
    await db.commit()

    # Phase 1: Sync fails with TokenExpiredError
    from backend.app.services.sync import sync_tenant
    from backend.app.integrations.quickbooks import TokenExpiredError

    with patch("backend.app.services.sync.get_profit_and_loss", new_callable=AsyncMock) as mock_pl:
        mock_pl.side_effect = TokenExpiredError("QBO access token expired")

        with pytest.raises(TokenExpiredError):
            await sync_tenant("t-err-001", db)

    # Verify: Integration is now disconnected
    assert db.store["integrations"][0].sync_status == "disconnected"
    assert "expired" in db.store["integrations"][0].error_message.lower()

    # Phase 2: Slack agent blocks with reconnect CTA
    from backend.app.services.slack_agent_runner import _check_qbo_data_freshness

    warning_msg, blocked = await _check_qbo_data_freshness("t-err-001", db)
    assert blocked is True
    assert "expired" in warning_msg.lower() or "reconnect" in warning_msg.lower()


# ────────────────────────────────────────────────────────────────
#  E2E: Stale data path
# ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_stale_data_warns_but_allows():
    """
    Data synced 72h ago → agent still runs but response includes warning banner.
    """
    from datetime import timedelta
    from backend.app.services.slack_agent_runner import _check_qbo_data_freshness

    db = InMemoryDB()

    tenant = Tenant(
        id="t-stale-001",
        clerk_org_id="stale_org",
        name="Stale Data Co",
        subscription_status="active",
        slack_team_id="T_STALE",
    )
    integration = Integration(
        id="int-stale-001",
        tenant_id="t-stale-001",
        provider="quickbooks",
        provider_connection_id="realm-stale",
        sync_status="active",
        last_synced_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    db.add(tenant)
    db.add(integration)
    await db.commit()

    warning_msg, blocked = await _check_qbo_data_freshness("t-stale-001", db)

    # Should warn but NOT block
    assert blocked is False
    assert warning_msg is not None
    assert "last synced" in warning_msg.lower()
    assert "3 days" in warning_msg.lower() or "72 hours" in warning_msg.lower()


# ────────────────────────────────────────────────────────────────
#  HTTP E2E: Stripe webhook → QBO redirect → Health check
# ────────────────────────────────────────────────────────────────

def test_e2e_http_health_and_stripe_webhook():
    """
    HTTP-level integration test via TestClient:
    Health check → Stripe webhook creates subscription.
    """

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()

    mock_tenant = Tenant(
        id="t-http-001", clerk_org_id="http_org", name="HTTP Test Co",
        subscription_status="trial",
    )
    mock_result.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_result

    async def override():
        yield mock_session

    app.dependency_overrides[get_session] = override

    try:
        client = TestClient(app, raise_server_exceptions=False)

        # Phase 1: Health check works
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        # Correlation ID is present
        assert "X-Correlation-ID" in health.headers

        # Phase 2: Stripe webhook processes checkout.session.completed
        mock_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"clerk_org_id": "http_org"},
                    "customer": "cus_http_001",
                    "subscription": "sub_http_001",
                }
            }
        }

        with patch("backend.app.api.v1.stripe.verify_webhook", return_value=mock_event):
            resp = client.post(
                "/api/v1/stripe/webhook",
                json=mock_event,
                headers={"stripe-signature": "dummy"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "success"

        # Verify: Tenant was updated
        assert mock_tenant.stripe_customer_id == "cus_http_001"
        assert mock_tenant.subscription_status == "active"

    finally:
        app.dependency_overrides.clear()
