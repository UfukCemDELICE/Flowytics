import logging
import jwt
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from slack_sdk.web.async_client import AsyncWebClient
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from backend.app.auth import get_current_user
from backend.app.database import get_session
from backend.app.models.tenant import Tenant
from backend.app.config import get_settings
from backend.app.integrations.slack import slack_app
from backend.app.services.slack_agent_runner import process_slack_message

router = APIRouter(prefix="/slack", tags=["slack"])
logger = logging.getLogger(__name__)

# Bolt Adapter
slack_handler = AsyncSlackRequestHandler(slack_app)

from slack_sdk.errors import SlackApiError
from starlette.responses import Response

@router.get("/install")
async def slack_install(user: dict = Depends(get_current_user)) -> dict:
    """Generate the 'Add to Slack' URL and redirect."""
    settings = get_settings()
    client_id = settings.SLACK_CLIENT_ID
    
    # We pass org_id in state to identify tenant in callback
    state = jwt.encode({"org_id": user["org_id"]}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")
    
    scopes = "chat:write,app_mentions:read,channels:history,groups:history,im:history"
    url = f"https://slack.com/oauth/v2/authorize?client_id={client_id}&scope={scopes}&state={state}"
    return {"auth_url": url}

@router.get("/oauth_redirect", response_class=RedirectResponse)
async def oauth_redirect(
    code: str = Query(...), 
    state: str = Query(...),
    session: AsyncSession = Depends(get_session)
) -> RedirectResponse:
    """Handle Slack OAuth callback, exchange code, map team to tenant."""
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.CLERK_SECRET_KEY[:32], algorithms=["HS256"])
        org_id = payload.get("org_id")
        if not org_id:
            raise ValueError("org_id missing")
    except Exception as e:
        logger.error(f"Slack OAuth state validation error: {e}")
        raise HTTPException(status_code=400, detail={"error": "invalid_state"})

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
        
    except SlackApiError as e:
        logger.error(f"Slack OAuth API error: {e.response['error']}")
        raise HTTPException(status_code=502, detail={"error": "slack_oauth_failed", "message": e.response['error']})
    except Exception as e:
        logger.error(f"Slack OAuth error: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "Failed to map Slack integration."})

@slack_app.event("app_mention")
async def handle_app_mentions(body: dict, say: callable, logger: logging.Logger) -> None: # type: ignore
    event = body.get("event", {})
    # Since we need a new DB session and background processing,
    # we'll offload the heavy lifting to our own async worker to avoid any timeout issues.
    asyncio.create_task(process_slack_message(event))

@router.post("/events")
async def slack_events(request: Request) -> Response:
    """Handle incoming Slack events via Bolt."""
    return await slack_handler.handle(request)

@router.post("/trigger_monthly_report")
async def trigger_monthly_report(tenant_id: int):
    """
    Diagnostic hidden endpoint to trigger the end-of-month AI generation
    for a specific tenant without waiting for the CRON schedule.
    """
    from backend.app.services.monthly_report import run_monthly_reports
    import asyncio
    
    # Run heavily in background so the request doesn't timeout hitting Claude
    asyncio.create_task(run_monthly_reports(tenant_id))
    return {"status": "dispatched", "message": f"Monthly report requested for Tenant ID {tenant_id}"}

