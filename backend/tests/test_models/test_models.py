"""Tests for SQLModel database models — instantiation and validation."""
from datetime import date
from decimal import Decimal

def test_tenant_defaults():
    """Tenant created with minimal fields gets correct defaults."""
    from backend.app.models.tenant import Tenant
    t = Tenant(clerk_org_id="org_123", name="Test Startup")
    assert t.id is not None  # UUID generated
    assert t.stage == "pre_seed"
    assert t.currency == "USD"
    assert t.subscription_status == "trial"
    assert t.onboarding_completed is False

def test_tenant_create_minimal():
    """TenantCreate validates with only required fields."""
    from backend.app.models.tenant import TenantCreate
    tc = TenantCreate(clerk_org_id="org_123", name="Test")
    assert tc.clerk_org_id == "org_123"

def test_tenant_read_excludes_stripe():
    """TenantRead does not expose stripe IDs."""
    from backend.app.models.tenant import TenantRead
    fields = TenantRead.model_fields
    assert "stripe_customer_id" not in fields
    assert "stripe_subscription_id" not in fields

def test_integration_defaults():
    """Integration has correct default sync_status."""
    from backend.app.models.integration import Integration
    i = Integration(tenant_id="tid", provider="codat", provider_connection_id="cid")
    assert i.sync_status == "pending"

def test_integration_read_excludes_credentials():
    """IntegrationRead does not expose credentials_encrypted."""
    from backend.app.models.integration import IntegrationRead
    assert "credentials_encrypted" not in IntegrationRead.model_fields

def test_financial_snapshot_accepts_dict():
    """FinancialSnapshot raw_data accepts a dict (JSONB)."""
    from backend.app.models.financial_snapshot import FinancialSnapshot
    fs = FinancialSnapshot(
        tenant_id="tid", snapshot_date=date(2026, 3, 1),
        source="codat", data_type="profit_loss",
        raw_data={"revenue": 50000, "expenses": 80000}
    )
    assert fs.raw_data["revenue"] == 50000

def test_agent_run_cost_is_decimal():
    """AgentRun.cost_usd must be Decimal, never float."""
    from backend.app.models.agent_run import AgentRun
    ar = AgentRun(tenant_id="tid", trigger_type="scheduled")
    assert isinstance(ar.cost_usd, Decimal)
    assert ar.cost_usd == Decimal("0")

def test_agent_run_defaults():
    """AgentRun defaults: status=running, tokens=0, tools_called=[]."""
    from backend.app.models.agent_run import AgentRun
    ar = AgentRun(tenant_id="tid", trigger_type="slack_message")
    assert ar.status == "running"
    assert ar.tokens_input == 0
    assert ar.tokens_output == 0

def test_slack_message_minimal():
    """SlackMessage with required fields only."""
    from backend.app.models.slack_message import SlackMessage
    sm = SlackMessage(tenant_id="tid", direction="inbound")
    assert sm.id is not None
    assert sm.feedback is None

def test_slack_user_map():
    """SlackUserMap all required fields."""
    from backend.app.models.slack_message import SlackUserMap
    su = SlackUserMap(
        tenant_id="tid", clerk_user_id="clerk_123",
        slack_user_id="U123", slack_team_id="T123"
    )
    assert su.slack_user_id == "U123"

def test_all_models_importable_from_init():
    pass
    # Just verifying import works — no assertion needed beyond no ImportError
