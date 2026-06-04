"""
Tests for the onboarding welcome message service.

Covers:
  - Idempotency: welcome not sent twice
  - Milestone gating: deferred if Slack or QBO not ready
  - Happy path: message sent when both milestones met
  - Block Kit content quality
  - Trigger integration from QBO first-sync callback
  - Trigger integration from Slack OAuth callback
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import UUID

from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.app.services.onboarding_welcome import (
    send_welcome_message_if_ready,
    _build_welcome_blocks,
    _check_and_send,
)

TEST_UUID = UUID("00000000-0000-0000-0000-000000000001")


# ── Block Kit content quality ───────────────────────────────────

def test_welcome_blocks_structure():
    """Verify the Block Kit payload has all required sections."""
    blocks = _build_welcome_blocks("Acme Inc")
    
    # Must have header, divider, intro, status fields, divider, CTA, context
    assert len(blocks) == 7
    assert blocks[0]["type"] == "header"
    assert "connected" in blocks[0]["text"]["text"].lower() or "✅" in blocks[0]["text"]["text"]
    assert blocks[1]["type"] == "divider"
    
    # Company name in intro
    assert "Acme Inc" in blocks[2]["text"]["text"]
    
    # Status fields
    assert blocks[3]["type"] == "section"
    assert "fields" in blocks[3]
    fields = blocks[3]["fields"]
    assert len(fields) == 4
    field_texts = " ".join(f["text"] for f in fields)
    assert "QuickBooks" in field_texts
    assert "Slack" in field_texts
    assert "24 hours" in field_texts
    assert "Monitoring" in field_texts or "Alerts" in field_texts
    
    # CTA section with example questions
    assert "burn rate" in blocks[5]["text"]["text"].lower()
    assert "runway" in blocks[5]["text"]["text"].lower()
    
    # Context footer
    assert blocks[6]["type"] == "context"
    assert "Flowytics" in blocks[6]["elements"][0]["text"]


def test_welcome_blocks_escapes_company_name():
    """Company names with special chars should not break Block Kit."""
    blocks = _build_welcome_blocks("O'Reilly & Sons <Corp>")
    # Should not crash
    assert "O'Reilly" in blocks[2]["text"]["text"]


# ── Milestone gating ────────────────────────────────────────────

def _mock_session_with(tenant, integration=None):
    """Build a mock session that returns tenant on first query, integration on second."""
    session = AsyncMock()
    # session.add is synchronous in SQLAlchemy
    session.add = MagicMock()
    
    mock_tenant_result = MagicMock()
    mock_tenant_result.scalar_one_or_none.return_value = tenant
    
    mock_integ_result = MagicMock()
    mock_integ_result.scalar_one_or_none.return_value = integration
    
    session.execute.side_effect = [mock_tenant_result, mock_integ_result]
    return session


@pytest.mark.asyncio
async def test_deferred_when_tenant_not_found():
    """If tenant doesn't exist, return False without sending."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    result = await _check_and_send("00000000-0000-0000-0000-000000000000", session)
    assert result is False


@pytest.mark.asyncio
async def test_idempotent_when_already_completed():
    """If onboarding_completed is True, don't send again."""
    tenant = Tenant(
        id=TEST_UUID, clerk_org_id="org-1", name="Test Co",
        slack_team_id="T123", onboarding_completed=True,
    )
    session = _mock_session_with(tenant)

    result = await _check_and_send(TEST_UUID, session)
    assert result is False


@pytest.mark.asyncio
async def test_deferred_when_slack_not_connected():
    """If Slack is not connected, defer the welcome."""
    tenant = Tenant(
        id=TEST_UUID, clerk_org_id="org-1", name="Test Co",
        slack_team_id=None, onboarding_completed=False,
    )
    session = _mock_session_with(tenant)

    result = await _check_and_send(TEST_UUID, session)
    assert result is False


@pytest.mark.asyncio
async def test_deferred_when_qbo_not_synced():
    """If QBO integration has never synced, defer the welcome."""
    tenant = Tenant(
        id=TEST_UUID, clerk_org_id="org-1", name="Test Co",
        slack_team_id="T123", onboarding_completed=False,
    )
    # Integration exists but last_synced_at is None → query returns None
    session = _mock_session_with(tenant, integration=None)

    result = await _check_and_send(TEST_UUID, session)
    assert result is False


# ── Happy path ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_welcome_sent_when_all_milestones_met():
    """When Slack + QBO are both ready, welcome should be sent and onboarding_completed set."""
    tenant = Tenant(
        id=TEST_UUID, clerk_org_id="org-1", name="Acme Inc",
        slack_team_id="T123", slack_channel_id="#general",
        onboarding_completed=False,
    )
    integration = Integration(
        id="int-1", tenant_id=TEST_UUID, provider="quickbooks",
        provider_connection_id="realm-1", sync_status="active",
        last_synced_at=datetime.now(timezone.utc),
    )
    session = _mock_session_with(tenant, integration)

    with patch("backend.app.services.onboarding_welcome.SlackClient") as MockClient:
        mock_instance = MagicMock()
        mock_instance.send_message = AsyncMock(return_value=True)
        MockClient.return_value = mock_instance

        result = await _check_and_send(TEST_UUID, session)

        assert result is True
        assert tenant.onboarding_completed is True
        mock_instance.send_message.assert_awaited_once()
        session.commit.assert_awaited()
        
        # Verify the channel used
        call_args = mock_instance.send_message.call_args
        assert call_args[0][0] == "#general"  # channel
        assert "connected" in call_args[0][1].lower() or "✅" in call_args[0][1]


@pytest.mark.asyncio
async def test_welcome_uses_general_when_no_channel_configured():
    """Falls back to #general when slack_channel_id is None."""
    tenant = Tenant(
        id=TEST_UUID, clerk_org_id="org-1", name="Test Co",
        slack_team_id="T123", slack_channel_id=None,
        onboarding_completed=False,
    )
    integration = Integration(
        id="int-1", tenant_id=TEST_UUID, provider="quickbooks",
        provider_connection_id="realm-1", sync_status="active",
        last_synced_at=datetime.now(timezone.utc),
    )
    session = _mock_session_with(tenant, integration)

    with patch("backend.app.services.onboarding_welcome.SlackClient") as MockClient:
        mock_instance = MagicMock()
        mock_instance.send_message = AsyncMock(return_value=True)
        MockClient.return_value = mock_instance

        result = await _check_and_send(TEST_UUID, session)

        assert result is True
        call_args = mock_instance.send_message.call_args
        assert call_args[0][0] == "#general"


@pytest.mark.asyncio
async def test_welcome_not_marked_complete_on_delivery_failure():
    """If Slack API fails, onboarding_completed stays False for retry."""
    tenant = Tenant(
        id=TEST_UUID, clerk_org_id="org-1", name="Test Co",
        slack_team_id="T123", onboarding_completed=False,
    )
    integration = Integration(
        id="int-1", tenant_id=TEST_UUID, provider="quickbooks",
        provider_connection_id="realm-1", sync_status="active",
        last_synced_at=datetime.now(timezone.utc),
    )
    session = _mock_session_with(tenant, integration)

    with patch("backend.app.services.onboarding_welcome.SlackClient") as MockClient:
        mock_instance = MagicMock()
        mock_instance.send_message = AsyncMock(return_value=False)  # Delivery failed
        MockClient.return_value = mock_instance

        result = await _check_and_send(TEST_UUID, session)

        assert result is False
        assert tenant.onboarding_completed is False  # Not marked, will retry


# ── Trigger integration ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_qbo_first_sync_triggers_welcome():
    """After QBO first-sync, welcome check fires and sends if Slack is ready."""
    from backend.app.api.v1.quickbooks import _background_first_sync

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.database._get_engine", return_value=(None, mock_session_factory)):
        with patch("backend.app.api.v1.quickbooks.sync_tenant", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"status": "synced", "snapshots_created": 3}
            with patch("backend.app.services.onboarding_welcome.send_welcome_message_if_ready", new_callable=AsyncMock) as mock_welcome:
                mock_welcome.return_value = True
                await _background_first_sync(TEST_UUID)
                mock_welcome.assert_awaited_once_with(TEST_UUID, mock_session)


@pytest.mark.asyncio
async def test_slack_oauth_triggers_welcome():
    """After Slack OAuth, _background_welcome_check fires send_welcome_message_if_ready."""
    from backend.app.api.v1.slack import _background_welcome_check

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.database._get_engine", return_value=(None, mock_session_factory)):
        with patch("backend.app.services.onboarding_welcome.send_welcome_message_if_ready", new_callable=AsyncMock) as mock_welcome:
            mock_welcome.return_value = True
            await _background_welcome_check(TEST_UUID)
            mock_welcome.assert_awaited_once_with(TEST_UUID, mock_session)


@pytest.mark.asyncio
async def test_welcome_import():
    """Smoke test: all imports work, no circular dependencies."""
    assert callable(send_welcome_message_if_ready)
