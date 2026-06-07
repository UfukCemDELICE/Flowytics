import pytest
import jwt
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlmodel import select
from sqlalchemy.exc import IntegrityError

from backend.app.main import app
from backend.app.config import get_settings
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB

class UniqueConstraintInMemoryDB(InMemoryDB):
    def __init__(self, raise_integrity_error_once=False):
        super().__init__()
        self.raise_integrity_error_once = raise_integrity_error_once
        self.rollback_called = False

    async def rollback(self):
        self.rollback_called = True
        self._pending.clear()

    async def commit(self):
        # Check unique constraint: (tenant_id, provider) on integrations table
        integrations = self.store.get("integrations", [])
        pending_integrations = [o for o in self._pending if getattr(o, "__tablename__", None) == "integrations"]
        
        if pending_integrations and self.raise_integrity_error_once:
            for p_integ in pending_integrations:
                for ext in integrations:
                    if ext.tenant_id == p_integ.tenant_id and ext.provider == p_integ.provider:
                        # Turn off the flag so that subsequent retry commits succeed
                        self.raise_integrity_error_once = False
                        raise IntegrityError("mock unique constraint violation (tenant_id, provider)", params=None, orig=None)

        await super().commit()

def test_quickbooks_callback_upsert_logic(client: TestClient):
    db = UniqueConstraintInMemoryDB(raise_integrity_error_once=False)
    
    tenant = Tenant(
        id="t-qbo-test-01",
        clerk_org_id="test_org_id",
        name="Test Company"
    )
    db.add(tenant)
    
    import asyncio
    asyncio.run(db.commit())

    # Mock settings
    settings = get_settings()
    state_token = jwt.encode({"org_id": "test_org_id"}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")

    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session

    # Mock OAuth client and token exchange
    mock_client = MagicMock()
    mock_client.access_token = "access-token-v1"
    mock_client.refresh_token = "refresh-token-v1"
    mock_client.expires_in = 3600
    mock_client.x_refresh_token_expires_in = 8726400

    # Mock background first sync
    with patch("backend.app.api.v1.quickbooks.quickbooks.get_auth_client", return_value=mock_client), \
         patch("backend.app.api.v1.quickbooks.quickbooks.get_fernet") as mock_fernet, \
         patch("backend.app.api.v1.quickbooks._background_first_sync", new_callable=AsyncMock) as mock_sync:
        
        mock_f = MagicMock()
        mock_f.encrypt.side_effect = lambda x: b"encrypted_" + x
        mock_f.decrypt.side_effect = lambda x: x[10:]
        mock_fernet.return_value = mock_f

        # --- CALL 1: Create Integration ---
        resp1 = client.get(f"/api/v1/quickbooks/callback?code=code1&realmId=realm123&state={state_token}", follow_redirects=False)
        assert resp1.status_code == 307  # Redirect response
        assert "/dashboard" in resp1.headers["location"]

        # Verify Integration created
        integrations = db.store.get("integrations", [])
        assert len(integrations) == 1
        integ1 = integrations[0]
        assert integ1.tenant_id == "t-qbo-test-01"
        assert integ1.provider == "quickbooks"
        assert integ1.provider_connection_id == "realm123"
        assert integ1.sync_status == "active"
        assert integ1.last_synced_at is None
        
        # Now update the token to simulate reconnect (CALL 2)
        mock_client.access_token = "access-token-v2"
        mock_client.refresh_token = "refresh-token-v2"
        
        # Set last_synced_at to a value to test it gets updated/reset to None
        from datetime import datetime, timezone
        integ1.last_synced_at = datetime.now(timezone.utc)
        
        resp2 = client.get(f"/api/v1/quickbooks/callback?code=code2&realmId=realm123&state={state_token}", follow_redirects=False)
        assert resp2.status_code == 307
        
        # Verify still only 1 Integration in the database (upsert instead of insert)
        integrations2 = db.store.get("integrations", [])
        assert len(integrations2) == 1
        integ2 = integrations2[0]
        assert integ2.tenant_id == "t-qbo-test-01"
        assert integ2.provider == "quickbooks"
        assert integ2.provider_connection_id == "realm123"
        assert integ2.sync_status == "active"
        # Verify last_synced_at is updated/reset to None
        assert integ2.last_synced_at is None

    app.dependency_overrides.clear()

def test_quickbooks_callback_integrity_error_upsert_fallback(client: TestClient):
    db = UniqueConstraintInMemoryDB(raise_integrity_error_once=True)
    
    tenant = Tenant(
        id="t-qbo-test-02",
        clerk_org_id="test_org_id_2",
        name="Test Company 2"
    )
    db.add(tenant)
    import asyncio
    asyncio.run(db.commit())

    # Pre-populate an integration row to trigger the "conflict" on insert
    existing_integ = Integration(
        id="existing-integ-id",
        tenant_id="t-qbo-test-02",
        provider="quickbooks",
        provider_connection_id="old_realm",
        credentials_encrypted="old_encrypted_credentials",
        sync_status="active"
    )
    db.add(existing_integ)
    asyncio.run(db.commit())

    settings = get_settings()
    state_token = jwt.encode({"org_id": "test_org_id_2"}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")

    async def override_get_session():
        yield db

    app.dependency_overrides[get_session] = override_get_session

    mock_client = MagicMock()
    mock_client.access_token = "access-token-new"
    mock_client.refresh_token = "refresh-token-new"
    mock_client.expires_in = 3600
    mock_client.x_refresh_token_expires_in = 8726400

    with patch("backend.app.api.v1.quickbooks.quickbooks.get_auth_client", return_value=mock_client), \
         patch("backend.app.api.v1.quickbooks.quickbooks.get_fernet") as mock_fernet, \
         patch("backend.app.api.v1.quickbooks._background_first_sync", new_callable=AsyncMock) as mock_sync:
        
        mock_f = MagicMock()
        mock_f.encrypt.side_effect = lambda x: b"encrypted_" + x
        mock_f.decrypt.side_effect = lambda x: x[10:]
        mock_fernet.return_value = mock_f

        # In handle_callback, the code will check if it exists using select(). 
        # To simulate a race condition where select() finds nothing but the row is inserted concurrently,
        # we can mock the select execution result to return None, so it tries to INSERT.
        original_execute = db.execute
        select_count = 0
        async def mock_execute(stmt):
            nonlocal select_count
            # If we query integrations table, return None to simulate "not found" on the first try
            if "integrations" in str(stmt):
                select_count += 1
                if select_count == 1:
                    return MagicMock(scalar_one_or_none=lambda: None)
            return await original_execute(stmt)
            
        db.execute = mock_execute

        resp = client.get(f"/api/v1/quickbooks/callback?code=code_new&realmId=realm_new&state={state_token}", follow_redirects=False)
        assert resp.status_code == 307
        
        # Verify the session rollback was called due to IntegrityError
        assert db.rollback_called is True
        
        # Verify the database has only 1 integration
        integrations = db.store.get("integrations", [])
        assert len(integrations) == 1
        integ = integrations[0]
        # And it should have the updated connection ID and encryption stub
        assert integ.provider_connection_id == "realm_new"
        assert integ.sync_status == "active"
        assert integ.last_synced_at is None

    app.dependency_overrides.clear()
