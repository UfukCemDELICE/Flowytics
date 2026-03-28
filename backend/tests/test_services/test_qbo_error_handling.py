"""
Tests for Sprint 6 MUSTs:
  - TokenExpiredError handling in QBO integration
  - Sync service disconnect vs error states
  - Stale data warning injection in Slack agent runner
  - Disconnected integration short-circuit
  - Background first-sync dispatch
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock

from backend.app.integrations.quickbooks import (
    IntegrationError,
    TokenExpiredError,
    auto_refresh_token,
)
from backend.app.models.integration import Integration
from backend.app.services.slack_agent_runner import (
    _check_qbo_data_freshness,
    STALE_DATA_THRESHOLD,
)


# ── TokenExpiredError hierarchy ─────────────────────────────────

def test_token_expired_is_integration_error():
    """TokenExpiredError must be a subclass of IntegrationError for broad catches."""
    err = TokenExpiredError("expired")
    assert isinstance(err, IntegrationError)
    assert isinstance(err, TokenExpiredError)


def test_integration_error_does_not_match_token_expired():
    """A plain IntegrationError must NOT be caught as TokenExpiredError."""
    err = IntegrationError("generic")
    assert not isinstance(err, TokenExpiredError)


# ── auto_refresh_token ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_refresh_raises_token_expired_on_missing_credentials():
    """If credentials_encrypted is None, auto_refresh_token should raise TokenExpiredError."""
    integration = Integration(
        id="int-1",
        tenant_id="t-1",
        provider="quickbooks",
        provider_connection_id="realm-1",
        credentials_encrypted=None,
        sync_status="active",
    )
    session = AsyncMock()
    with pytest.raises(TokenExpiredError, match="No credentials stored"):
        await auto_refresh_token(integration, session)


@pytest.mark.asyncio
async def test_auto_refresh_marks_disconnected_on_refresh_failure():
    """When the Intuit refresh call fails, integration must become 'disconnected'."""
    import json, base64, hashlib
    from cryptography.fernet import Fernet

    # Build valid encrypted tokens with an old timestamp to trigger refresh path
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    tokens = {
        "access_token": "old_at",
        "refresh_token": "old_rt",
        "expires_in": 3600,
        "x_refresh_token_expires_in": 8726400,
        "realm_id": "realm-1",
        "updated_at": old_time,
    }

    with patch("backend.app.integrations.quickbooks.settings") as mock_settings:
        mock_settings.CLERK_SECRET_KEY = "test_secret_key_32_chars_longggg"
        mock_settings.FERNET_KEY = ""  # Force SHA-256 fallback
        mock_settings.QB_CLIENT_ID = "cid"
        mock_settings.QB_CLIENT_SECRET = "csec"
        mock_settings.QB_REDIRECT_URI = "http://localhost"
        mock_settings.QB_ENVIRONMENT = "sandbox"

        key = hashlib.sha256(mock_settings.CLERK_SECRET_KEY.encode()).digest()
        fernet = Fernet(base64.urlsafe_b64encode(key))
        encrypted = fernet.encrypt(json.dumps(tokens).encode()).decode()

        integration = Integration(
            id="int-1",
            tenant_id="t-1",
            provider="quickbooks",
            provider_connection_id="realm-1",
            credentials_encrypted=encrypted,
            sync_status="active",
        )

        session = AsyncMock()

        with patch("backend.app.integrations.quickbooks.get_auth_client") as mock_auth:
            mock_client = MagicMock()
            mock_client.refresh.side_effect = Exception("Refresh token revoked")
            mock_auth.return_value = mock_client

            with pytest.raises(TokenExpiredError, match="connection expired"):
                await auto_refresh_token(integration, session)

            # Integration must be marked disconnected
            assert integration.sync_status == "disconnected"
            assert "Token refresh failed" in integration.error_message
            session.commit.assert_awaited()


# ── _check_qbo_data_freshness ───────────────────────────────────

@pytest.mark.asyncio
async def test_freshness_no_integration():
    """No QBO integration → blocking warning."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    msg, blocked = await _check_qbo_data_freshness("tenant-1", session)
    assert blocked is True
    assert "No QuickBooks account connected" in msg


@pytest.mark.asyncio
async def test_freshness_disconnected():
    """Disconnected integration → blocking reconnect CTA."""
    integration = Integration(
        id="int-1", tenant_id="t-1", provider="quickbooks",
        provider_connection_id="r1", sync_status="disconnected",
    )
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = integration
    session.execute.return_value = mock_result

    msg, blocked = await _check_qbo_data_freshness("t-1", session)
    assert blocked is True
    assert "expired" in msg.lower() or "reconnect" in msg.lower()


@pytest.mark.asyncio
async def test_freshness_never_synced():
    """Integration exists but never synced → blocking wait message."""
    integration = Integration(
        id="int-1", tenant_id="t-1", provider="quickbooks",
        provider_connection_id="r1", sync_status="active",
        last_synced_at=None,
    )
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = integration
    session.execute.return_value = mock_result

    msg, blocked = await _check_qbo_data_freshness("t-1", session)
    assert blocked is True
    assert "no data has been synced" in msg.lower()


@pytest.mark.asyncio
async def test_freshness_stale_data_warns():
    """Data older than threshold → warning but NOT blocked."""
    integration = Integration(
        id="int-1", tenant_id="t-1", provider="quickbooks",
        provider_connection_id="r1", sync_status="active",
        last_synced_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = integration
    session.execute.return_value = mock_result

    msg, blocked = await _check_qbo_data_freshness("t-1", session)
    assert blocked is False
    assert msg is not None
    assert "last synced" in msg.lower()


@pytest.mark.asyncio
async def test_freshness_fresh_data_ok():
    """Data synced within threshold → no warning, not blocked."""
    integration = Integration(
        id="int-1", tenant_id="t-1", provider="quickbooks",
        provider_connection_id="r1", sync_status="active",
        last_synced_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = integration
    session.execute.return_value = mock_result

    msg, blocked = await _check_qbo_data_freshness("t-1", session)
    assert blocked is False
    assert msg is None


# ── Background first-sync ───────────────────────────────────────

@pytest.mark.asyncio
async def test_background_first_sync_calls_sync_tenant():
    """_background_first_sync should call sync_tenant in an independent session."""
    from backend.app.api.v1.quickbooks import _background_first_sync

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.database._get_engine", return_value=(None, mock_session_factory)):
        with patch("backend.app.api.v1.quickbooks.sync_tenant", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = {"status": "synced", "snapshots_created": 3}
            with patch("backend.app.services.onboarding_welcome.send_welcome_message_if_ready", new_callable=AsyncMock):
                await _background_first_sync("org-123")
                mock_sync.assert_awaited_once_with("org-123", mock_session)


@pytest.mark.asyncio
async def test_background_first_sync_handles_failure_gracefully():
    """_background_first_sync must not raise even if sync_tenant fails."""
    from backend.app.api.v1.quickbooks import _background_first_sync

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("backend.app.database._get_engine", return_value=(None, mock_session_factory)):
        with patch("backend.app.api.v1.quickbooks.sync_tenant", new_callable=AsyncMock) as mock_sync:
            mock_sync.side_effect = Exception("QBO is down")
            # Should NOT raise
            await _background_first_sync("org-123")
