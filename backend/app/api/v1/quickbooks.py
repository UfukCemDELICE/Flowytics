from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import get_current_user
from backend.app.database import get_session
from backend.app.integrations import quickbooks
from backend.app.services.sync import sync_tenant

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])

@router.get("/auth")
async def get_auth_url(user: dict = Depends(get_current_user)):
    """Return QuickBooks OAuth URL."""
    url = quickbooks.generate_auth_url()
    return {"auth_url": url}

@router.get("/callback")
async def oauth_callback(
    code: str = Query(...), 
    realmId: str = Query(...),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Exchange code for tokens and save them."""
    try:
        await quickbooks.handle_callback(code, realmId, user["org_id"], session)
        return {"status": "success", "message": "QuickBooks connected successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")

@router.post("/sync")
async def sync_quickbooks_data(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Trigger a manual sync of QuickBooks data for the current tenant."""
    try:
        result = await sync_tenant(user["org_id"], session)
        return result
    except quickbooks.IntegrationError as e:
        raise HTTPException(status_code=502, detail=f"Integration Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")
