import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration

def test_disconnect_quickbooks_success(auth_client: TestClient):
    # Mock tenant and integration
    mock_tenant = Tenant(
        id="t-qbo-001",
        clerk_org_id="test_org_id",
        name="Test Company"
    )
    mock_integration = Integration(
        id="i-qbo-001",
        tenant_id="t-qbo-001",
        provider="quickbooks",
        provider_connection_id="realm-001"
    )
    
    mock_session = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()
    
    # We execute two queries:
    # 1. select(Tenant)
    # 2. select(Integration)
    mock_res_tenant = MagicMock()
    mock_res_tenant.scalar_one_or_none.return_value = mock_tenant
    
    mock_res_integ = MagicMock()
    mock_res_integ.scalar_one_or_none.return_value = mock_integration
    
    mock_session.execute.side_effect = [mock_res_tenant, mock_res_integ]
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = auth_client.delete("/api/v1/quickbooks/disconnect")
        assert resp.status_code == 200
        assert resp.json() == {"status": "disconnected"}
        mock_session.delete.assert_called_once_with(mock_integration)
        mock_session.commit.assert_called_once()
    finally:
        del app.dependency_overrides[get_session]


def test_disconnect_quickbooks_not_connected(auth_client: TestClient):
    # Mock tenant but no integration
    mock_tenant = Tenant(
        id="t-qbo-001",
        clerk_org_id="test_org_id",
        name="Test Company"
    )
    
    mock_session = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()
    
    mock_res_tenant = MagicMock()
    mock_res_tenant.scalar_one_or_none.return_value = mock_tenant
    
    mock_res_integ = MagicMock()
    mock_res_integ.scalar_one_or_none.return_value = None
    
    mock_session.execute.side_effect = [mock_res_tenant, mock_res_integ]
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = auth_client.delete("/api/v1/quickbooks/disconnect")
        assert resp.status_code == 200
        assert resp.json() == {"status": "not_connected"}
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
    finally:
        del app.dependency_overrides[get_session]


def test_disconnect_slack_success(auth_client: TestClient):
    # Mock tenant
    mock_tenant = Tenant(
        id="t-slack-001",
        clerk_org_id="test_org_id",
        name="Test Company",
        slack_team_id="T_SLACK",
        slack_channel_id="C_SLACK"
    )
    
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    
    mock_res_tenant = MagicMock()
    mock_res_tenant.scalar_one_or_none.return_value = mock_tenant
    
    mock_session.execute.return_value = mock_res_tenant
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = auth_client.delete("/api/v1/slack/disconnect")
        assert resp.status_code == 200
        assert resp.json() == {"status": "disconnected"}
        assert mock_tenant.slack_team_id is None
        assert mock_tenant.slack_channel_id is None
        mock_session.add.assert_called_once_with(mock_tenant)
        mock_session.commit.assert_called_once()
    finally:
        del app.dependency_overrides[get_session]


def test_disconnect_tenant_not_found(auth_client: TestClient):
    mock_session = AsyncMock()
    mock_res_tenant = MagicMock()
    mock_res_tenant.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res_tenant
    
    async def override_get_session():
        yield mock_session
        
    app.dependency_overrides[get_session] = override_get_session
    try:
        resp = auth_client.delete("/api/v1/quickbooks/disconnect")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Tenant not found"}
    finally:
        del app.dependency_overrides[get_session]
