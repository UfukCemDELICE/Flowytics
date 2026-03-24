import logging
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from slack_sdk.web.async_client import AsyncWebClient

from backend.app.auth import get_current_user
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.config import get_settings

router = APIRouter(prefix="/slack", tags=["slack"])
logger = logging.getLogger(__name__)

@router.get("/install")
async def slack_install(user: dict = Depends(get_current_user)):
    """Generate the 'Add to Slack' URL and redirect."""
    settings = get_settings()
    client_id = settings.SLACK_CLIENT_ID
    
    # We pass org_id in state to identify tenant in callback
    state = jwt.encode({"org_id": user["org_id"]}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")
    
    scopes = "chat:write,app_mentions:read,channels:history,groups:history,im:history"
    url = f"https://slack.com/oauth/v2/authorize?client_id={client_id}&scope={scopes}&state={state}"
    return {"auth_url": url}

@router.get("/oauth_redirect")
async def oauth_redirect(
    code: str = Query(...), 
    state: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """Handle Slack OAuth callback, exchange code, map team to tenant."""
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.CLERK_SECRET_KEY[:32], algorithms=["HS256"])
        org_id = payload["org_id"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state token")

    client = AsyncWebClient()
    try:
        response = await client.oauth_v2_access(
            client_id=settings.SLACK_CLIENT_ID,
            client_secret=settings.SLACK_CLIENT_SECRET,
            code=code
        )
        team_id = response.get("team", {}).get("id")
        
        # We don't save the bot token currently (assuming single global workspace for MVP)
        # We just map the team_id to the tenant
        stmt = select(Tenant).where(Tenant.clerk_org_id == org_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if tenant:
            tenant.slack_team_id = team_id
            session.add(tenant)
            await session.commit()
            
        return RedirectResponse(url="http://localhost:3000/dashboard")
        
    except Exception as e:
        logger.error(f"Slack OAuth error: {e}")
        raise HTTPException(status_code=400, detail="Slack installation failed.")

@router.post("/events")
async def slack_events(request: Request):
    """Handle incoming Slack events (mentions, messages) via Events API."""
    # Note: Signature verification should be implemented here in production
    payload = await request.json()
    
    # URL Verification for Slack
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
        
    event = payload.get("event", {})
    if event.get("type") == "app_mention":
        # Pass to the background LangGraph AI CFO task here
        logger.info(f"Bot mentioned by user {event.get('user')} in channel {event.get('channel')}")
        # e.g., background_tasks.add_task(process_slack_message, event)
        
    return {"status": "ok"}
