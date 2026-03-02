import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from supabase import create_client

from backend.app.auth import get_current_user_id
from backend.app.config import get_settings
from backend.app.integrations.quickbooks import QuickBooksClient

router = APIRouter(prefix="/quickbooks", tags=["quickbooks"])


def _get_supabase():
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


@router.get("/authorize")
async def authorize(user_id: str = Depends(get_current_user_id)) -> dict:
    """Start QuickBooks OAuth flow. Returns authorization URL for the frontend to redirect to."""
    state = f"{user_id}:{secrets.token_urlsafe(16)}"
    url = QuickBooksClient.get_authorization_url(state=state)
    return {"authorization_url": url}


@router.get("/callback")
async def callback(request: Request) -> RedirectResponse:
    """
    Handle QuickBooks OAuth callback.
    Exchanges authorization code for tokens and stores them in Supabase.
    """
    code = request.query_params.get("code")
    realm_id = request.query_params.get("realmId")
    state = request.query_params.get("state", "")

    if not code or not realm_id:
        raise HTTPException(status_code=400, detail="Missing code or realmId in callback.")

    # State format: "{clerk_user_id}:{random}"
    user_id = state.split(":")[0] if ":" in state else ""
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid state parameter.")

    token = await QuickBooksClient.exchange_code(code=code, realm_id=realm_id)
    token.user_id = user_id

    from backend.app.services.financial import FinancialService
    db = _get_supabase()
    svc = FinancialService(db)
    await svc.save_qb_token(token)

    settings = get_settings()
    frontend_url = getattr(settings, "frontend_url", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/dashboard?qb_connected=1")


@router.delete("/disconnect")
async def disconnect(user_id: str = Depends(get_current_user_id)) -> dict:
    """Remove stored QuickBooks tokens and clear cache for the user."""
    from backend.app.services.financial import FinancialService
    from backend.app.services.cache import QBCache

    db = _get_supabase()
    svc = FinancialService(db)
    await svc.delete_qb_token(user_id)

    # Clear all cached QB data for this user
    db.table("qb_cache").delete().eq("user_id", user_id).execute()

    return {"user_id": user_id, "status": "disconnected"}


@router.get("/status")
async def connection_status(user_id: str = Depends(get_current_user_id)) -> dict:
    """Check whether QuickBooks is connected for the current user."""
    from backend.app.services.financial import FinancialService

    db = _get_supabase()
    svc = FinancialService(db)
    token = await svc.get_qb_token(user_id)

    return {
        "user_id": user_id,
        "connected": token is not None,
        "realm_id": token.realm_id if token else None,
    }
