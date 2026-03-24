from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import get_current_user
from backend.app.database import get_session
from backend.app.integrations import quickbooks
from backend.app.services.sync import sync_tenant

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])

import jwt
from backend.app.config import get_settings

@router.get("/auth")
async def get_auth_url(user: dict = Depends(get_current_user)):
    """Return QuickBooks OAuth URL."""
    settings = get_settings()
    # Safely encode the org_id in the state param to survive the OAuth roundtrip
    state = jwt.encode({"org_id": user["org_id"]}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")
    url = quickbooks.generate_auth_url(state)
    return {"auth_url": url}

@router.get("/callback")
async def oauth_callback(
    code: str = Query(...), 
    realmId: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """Exchange code for tokens and save them."""
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.CLERK_SECRET_KEY[:32], algorithms=["HS256"])
        org_id = payload["org_id"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state token in OAuth callback")

    try:
        await quickbooks.handle_callback(code, realmId, org_id, session)
        return RedirectResponse(url="http://localhost:3000/dashboard")
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
