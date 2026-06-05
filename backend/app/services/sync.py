from datetime import datetime, timezone
import logging
from dateutil.relativedelta import relativedelta
from backend.app.utils import utc_now
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import delete
from backend.app.models.integration import Integration
from backend.app.models.financial_snapshot import FinancialSnapshot
from backend.app.models.tenant import Tenant
from backend.app.integrations.quickbooks import (
    get_profit_and_loss,
    get_balance_sheet,
    get_cash_flow,
    IntegrationError,
    TokenExpiredError,
)

logger = logging.getLogger(__name__)

async def sync_tenant(tenant_id: str, session: AsyncSession) -> dict:
    """Pull P&L, Balance Sheet, and Cash Flow from QBO for the last 12 months, save to DB."""
    stmt = select(Integration).where(
        Integration.tenant_id == tenant_id,
        Integration.provider == "quickbooks",
        Integration.sync_status.in_(["active", "error"]),  # Allow retry from error state
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise IntegrationError("No active QuickBooks integration found for tenant")
        
    realm_id = integration.provider_connection_id
    
    # Fetch tenant to calculate dynamic start_date
    from uuid import UUID
    try:
        t_id = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    except ValueError:
        t_id = tenant_id

    tenant_stmt = select(Tenant).where(Tenant.id == t_id)
    tenant_res = await session.execute(tenant_stmt)
    tenant = tenant_res.scalar_one_or_none()

    today = datetime.now(timezone.utc).date()
    two_years_ago = today - relativedelta(years=2)

    if tenant and tenant.created_at:
        tenant_created = tenant.created_at.date() if hasattr(tenant.created_at, "date") else tenant.created_at
        start_date = min(tenant_created, two_years_ago)
    else:
        start_date = two_years_ago

    start_date_str = start_date.isoformat()
    end_date_str = today.isoformat()
    
    try:
        # Pull reports from QBO
        pl_data = await get_profit_and_loss(realm_id, start_date_str, end_date_str, str(tenant_id), session)
        bs_data = await get_balance_sheet(realm_id, start_date_str, end_date_str, str(tenant_id), session)
        cf_data = await get_cash_flow(realm_id, start_date_str, end_date_str, str(tenant_id), session)
        
        # Save snapshots
        snapshots = [
            FinancialSnapshot(
                tenant_id=tenant_id,
                snapshot_date=today,
                source="quickbooks",
                data_type="profit_loss",
                raw_data=pl_data,
                period_start=start_date,
                period_end=today
            ),
            FinancialSnapshot(
                tenant_id=tenant_id,
                snapshot_date=today,
                source="quickbooks",
                data_type="balance_sheet",
                raw_data=bs_data,
                period_start=start_date,
                period_end=today
            ),
            FinancialSnapshot(
                tenant_id=tenant_id,
                snapshot_date=today,
                source="quickbooks",
                data_type="cash_flow",
                raw_data=cf_data,
                period_start=start_date,
                period_end=today
            )
        ]
        
        for snap in snapshots:
            delete_stmt = delete(FinancialSnapshot).where(
                FinancialSnapshot.tenant_id == tenant_id,
                FinancialSnapshot.data_type == snap.data_type,
                FinancialSnapshot.snapshot_date == snap.snapshot_date,
            )
            await session.execute(delete_stmt)
            session.add(snap)
            
        # Update integration status
        integration.last_synced_at = utc_now()
        integration.sync_status = "active"
        
        await session.commit()
        return {"status": "synced", "snapshots_created": len(snapshots)}
        
    except TokenExpiredError as e:
        logger.error(
            "QBO token expired during sync",
            extra={"tenant_id": tenant_id, "error_type": "token_expired", "provider": "quickbooks"},
            exc_info=True,
        )
        integration.sync_status = "disconnected"
        integration.error_message = str(e)
        await session.commit()
        raise

    except IntegrationError as e:
        logger.error(
            "Sync failed for tenant",
            extra={"tenant_id": tenant_id, "error_type": "integration_error", "provider": "quickbooks"},
            exc_info=True,
        )
        integration.sync_status = "error"
        integration.error_message = str(e)
        await session.commit()
        raise
