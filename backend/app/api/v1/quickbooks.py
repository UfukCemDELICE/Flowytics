import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
import jwt

from backend.app.auth import get_current_user
from backend.app.database import get_session
from backend.app.integrations import quickbooks
from backend.app.services.sync import sync_tenant
from backend.app.config import get_settings
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])
logger = logging.getLogger(__name__)


async def _background_first_sync(tenant_id: UUID):
    """Background task: pull QBO data immediately after OAuth connect."""
    from backend.app.database import _get_engine
    from backend.app.services.onboarding_welcome import send_welcome_message_if_ready
    _, session_factory = _get_engine()
    async with session_factory() as bg_session:
        try:
            result = await sync_tenant(tenant_id, bg_session)
            logger.info(f"Auto first-sync completed for tenant {tenant_id}: {result}")
            # Check if all onboarding milestones are met → send welcome
            await send_welcome_message_if_ready(tenant_id, bg_session)
        except Exception as e:
            logger.error(f"Auto first-sync failed for tenant {tenant_id}: {e}")


@router.get("/auth")
async def get_auth_url(user: dict = Depends(get_current_user)):
    """Return QuickBooks OAuth URL."""
    settings = get_settings()
    # Safely encode the org_id in the state param to survive the OAuth roundtrip
    state = jwt.encode({"org_id": user["org_id"]}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")
    url = quickbooks.generate_auth_url(state)
    return {"auth_url": url}

@router.get("/callback", response_class=RedirectResponse, response_model=None)
async def oauth_callback(
    code: str = Query(...), 
    realmId: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> dict | RedirectResponse:
    """Exchange code for tokens, save them, and trigger background data sync."""
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.CLERK_SECRET_KEY[:32], algorithms=["HS256"])
        org_id = payload.get("org_id")
        if not org_id:
            raise ValueError("org_id missing in token")
    except Exception as e:
        logger.warning(f"QBO OAuth state validation failed: {e}")
        raise HTTPException(
            status_code=400, 
            detail={"error": "invalid_state", "message": "OAuth state token is invalid or expired."}
        )

    try:
        # Resolve Clerk org_id to Tenant.id (UUID)
        stmt = select(Tenant).where(Tenant.clerk_org_id == org_id)
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"No tenant found for clerk org ID: {org_id}")

        await quickbooks.handle_callback(code, realmId, tenant.id, session)
        # Fire background sync — user sees dashboard instantly, data populates async
        asyncio.create_task(_background_first_sync(tenant.id))
        return RedirectResponse(url="http://localhost:3000/dashboard")
    except quickbooks.IntegrationError as e:
        logger.error(f"QBO callback upstream error: {e}")
        raise HTTPException(status_code=502, detail={"error": "upstream_error", "message": "Could not connect to QuickBooks. Please try again."})
    except Exception:
        logger.exception("QuickBooks OAuth callback failed with unexpected error")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "QuickBooks OAuth exchange failed."})

@router.post("/sync")
async def sync_quickbooks_data(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Trigger a manual sync of QuickBooks data for the current tenant."""
    try:
        # Resolve user["org_id"] to Tenant database UUID
        stmt = select(Tenant).where(Tenant.clerk_org_id == user["org_id"])
        res = await session.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        result = await sync_tenant(tenant.id, session)
        return result
    except quickbooks.IntegrationError as e:
        logger.error(f"QBO sync integration error for org {user['org_id']}: {e}")
        raise HTTPException(status_code=502, detail={"error": "integration_error", "message": "QuickBooks sync failed. Please reconnect if the problem persists."})
    except Exception as e:
        logger.error(f"QBO sync internal error for org {user['org_id']}: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "An unexpected error occurred during sync."})

@router.delete("/disconnect")
async def disconnect_quickbooks(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Disconnect QuickBooks Online by deleting the integration record."""
    stmt = select(Tenant).where(Tenant.clerk_org_id == user["org_id"])
    res = await session.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    integ_stmt = select(Integration).where(
        Integration.tenant_id == tenant.id,
        Integration.provider == "quickbooks"
    )
    res = await session.execute(integ_stmt)
    integration = res.scalar_one_or_none()
    if integration:
        await session.delete(integration)
        await session.commit()
        return {"status": "disconnected"}
    return {"status": "not_connected"}
