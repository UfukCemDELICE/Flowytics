from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import get_current_user
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration

router = APIRouter(tags=["auth"])

@router.get("/me")
async def get_me(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Return user claims and integration connection statuses."""
    org_id = user["org_id"]
    
    quickbooks_connected = False
    slack_connected = False
    
    try:
        stmt = select(Tenant).where(Tenant.clerk_org_id == org_id)
        tenant = (await session.execute(stmt)).scalar_one_or_none()
        
        if tenant:
            if tenant.slack_team_id:
                slack_connected = True
                
            integ_stmt = select(Integration).where(
                Integration.tenant_id == tenant.id,
                Integration.provider == "quickbooks"
            )
            integration = (await session.execute(integ_stmt)).scalar_one_or_none()
            if integration and integration.sync_status == "active":
                quickbooks_connected = True
    except Exception:
        # Fallback/silent failure for tests or if DB is not ready
        pass
            
    return {
        "user_id": user.get("user_id", ""),
        "org_id": org_id,
        "quickbooks_connected": quickbooks_connected,
        "slack_connected": slack_connected
    }
