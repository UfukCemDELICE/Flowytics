import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.services.sync import run_daily_qbo_sync
from backend.app.services.computed_metrics import run_daily_computed_metrics
from backend.app.models.integration import Integration
from backend.app.models.financial_snapshot import FinancialSnapshot
from backend.app.models.computed_metric import ComputedMetric
from backend.tests.test_e2e.test_e2e_lifecycle import InMemoryDB, InMemoryResult

@pytest.mark.asyncio
async def test_run_daily_qbo_sync_success_and_failure():
    # Setup test DB
    db = InMemoryDB()
    
    tenant1_id = uuid4()
    tenant2_id = uuid4()
    
    # Add active integration
    integration1 = Integration(
        id=uuid4(),
        tenant_id=tenant1_id,
        provider="quickbooks",
        provider_connection_id="realm_1",
        sync_status="active"
    )
    # Add error status integration
    integration2 = Integration(
        id=uuid4(),
        tenant_id=tenant2_id,
        provider="quickbooks",
        provider_connection_id="realm_2",
        sync_status="error"
    )
    # Add disconnected status integration (should not sync)
    integration3 = Integration(
        id=uuid4(),
        tenant_id=uuid4(),
        provider="quickbooks",
        provider_connection_id="realm_3",
        sync_status="disconnected"
    )
    
    db.store["integrations"] = [integration1, integration2, integration3]
    
    # Mock execute to return integrations list correctly
    async def mock_execute(stmt):
        if "integrations" in str(stmt).lower():
            return InMemoryResult([integration1, integration2])
        return InMemoryResult(db._execute_sync(stmt))
    db.execute = mock_execute
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch("backend.app.services.sync._get_engine", return_value=(None, mock_session_factory)), \
         patch("backend.app.services.sync.sync_tenant", new_callable=AsyncMock) as mock_sync_tenant:
         
        # Make one succeed and one fail
        async def mock_sync(tenant_id, session):
            if str(tenant_id) == str(tenant2_id):
                raise Exception("Sync failed")
            return {"status": "synced"}
            
        mock_sync_tenant.side_effect = mock_sync
        
        await run_daily_qbo_sync()
        
        # Verify sync_tenant called for tenant1 and tenant2, but not tenant3
        assert mock_sync_tenant.call_count == 2
        called_tenant_ids = {str(call[0][0]) for call in mock_sync_tenant.call_args_list}
        assert called_tenant_ids == {str(tenant1_id), str(tenant2_id)}

@pytest.mark.asyncio
async def test_run_daily_computed_metrics_execution():
    db = InMemoryDB()
    tenant_id = uuid4()
    
    # Active integration
    integration = Integration(
        id=uuid4(),
        tenant_id=tenant_id,
        provider="quickbooks",
        provider_connection_id="realm_1",
        sync_status="active"
    )
    
    # Snapshots
    pl_snapshot = FinancialSnapshot(
        id=uuid4(),
        tenant_id=tenant_id,
        snapshot_date=datetime.now(timezone.utc).date(),
        source="quickbooks",
        data_type="profit_loss",
        raw_data={"monthly_data": [{"month": "2026-05", "revenue": 100, "expenses": 80, "net_income": 20}]}
    )
    bs_snapshot = FinancialSnapshot(
        id=uuid4(),
        tenant_id=tenant_id,
        snapshot_date=datetime.now(timezone.utc).date(),
        source="quickbooks",
        data_type="balance_sheet",
        raw_data={"current_cash_balance": 1000}
    )
    
    db.store["integrations"] = [integration]
    db.store["financial_snapshots"] = [pl_snapshot, bs_snapshot]
    db.store["computed_metrics"] = []
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    
    # Mock database execute to correctly return snapshots on select
    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        if "financial_snapshots" in stmt_str:
            if "profit_loss" in stmt_str:
                return InMemoryResult(pl_snapshot)
            elif "balance_sheet" in stmt_str:
                return InMemoryResult(bs_snapshot)
        return InMemoryResult(db._execute_sync(stmt))
        
    db.execute = mock_execute
    
    with patch("backend.app.services.computed_metrics._get_engine", return_value=(None, mock_session_factory)):
        # Run daily computed metrics
        await run_daily_computed_metrics()
        
        # Verify computed metrics were added to db.store
        stored_metrics = db.store.get("computed_metrics", [])
        assert len(stored_metrics) == 3
        
        metric_types = {m.metric_type for m in stored_metrics}
        assert metric_types == {"burn_rate", "runway", "cash_forecast"}
        
        # Check burn rate metric values
        burn_metric = next(m for m in stored_metrics if m.metric_type == "burn_rate")
        assert burn_metric.tenant_id == tenant_id
        assert burn_metric.period == datetime.now(timezone.utc).strftime("%Y-%m")
        assert burn_metric.value["net_burn_monthly"] == "-20"
