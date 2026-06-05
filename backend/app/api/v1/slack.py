import os
import re
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


async def _background_welcome_check(tenant_id: str):
    """Background task: check if welcome message should be sent after Slack connect."""
    from backend.app.database import _get_engine
    from backend.app.services.onboarding_welcome import send_welcome_message_if_ready
    _, session_factory = _get_engine()
    async with session_factory() as bg_session:
        try:
            await send_welcome_message_if_ready(tenant_id, bg_session)
        except Exception as e:
            logger.error(f"Welcome check failed after Slack connect for tenant {tenant_id}: {e}")


async def _background_member_joined_handler(team_id: str):
    """Background task to handle bot joining a channel: find tenant and check welcome message."""
    from backend.app.database import _get_engine
    from backend.app.models.tenant import Tenant
    from backend.app.models.integration import Integration
    from backend.app.models.slack_message import SlackUserMap
    from backend.app.services.onboarding_welcome import send_welcome_message_if_ready
    
    _, session_factory = _get_engine()
    async with session_factory() as session:
        try:
            tenant_id = None
            
            # 1. Try SlackUserMap
            map_stmt = select(SlackUserMap).where(SlackUserMap.slack_team_id == team_id)
            map_res = await session.execute(map_stmt)
            slack_map = map_res.scalar_one_or_none()
            if slack_map and slack_map.tenant_id:
                tenant_id = slack_map.tenant_id
                
            # 2. Try Integration (provider="slack")
            if not tenant_id:
                integ_stmt = select(Integration).where(
                    Integration.provider == "slack",
                    Integration.provider_connection_id == team_id
                )
                integ_res = await session.execute(integ_stmt)
                integration = integ_res.scalar_one_or_none()
                if integration and integration.tenant_id:
                    tenant_id = integration.tenant_id

            # 3. Try Tenant directly
            if not tenant_id:
                tenant_stmt = select(Tenant).where(Tenant.slack_team_id == team_id)
                tenant_res = await session.execute(tenant_stmt)
                tenant = tenant_res.scalar_one_or_none()
                if tenant:
                    tenant_id = tenant.id
                    
            if not tenant_id:
                logger.warning(f"member_joined_channel: No tenant found for slack_team_id {team_id}")
                return
                
            await send_welcome_message_if_ready(tenant_id, session)
            
        except Exception as e:
            logger.error(f"Failed to process member_joined_channel for team {team_id}: {e}")

# Bolt Adapter
slack_handler = AsyncSlackRequestHandler(slack_app)

from slack_sdk.errors import SlackApiError
from starlette.responses import Response

@router.get("/install")
async def slack_install(user: dict = Depends(get_current_user)):
    settings = get_settings()
    client_id = settings.SLACK_CLIENT_ID
    state = jwt.encode({"org_id": user["org_id"]}, settings.CLERK_SECRET_KEY[:32], algorithm="HS256")
    scopes = "chat:write,app_mentions:read,channels:history,groups:history,im:history"
    redirect_uri = settings.SLACK_REDIRECT_URI
    slack_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return {"auth_url": slack_url}

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
            code=code,
            redirect_uri = settings.SLACK_REDIRECT_URI 
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
            # Check if all onboarding milestones are met → send welcome
            asyncio.create_task(_background_welcome_check(str(tenant.id)))
            
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard")
        
    except SlackApiError as e:
        logger.error(f"Slack OAuth API error: {e.response['error']}")
        raise HTTPException(status_code=502, detail={"error": "slack_oauth_failed", "message": e.response['error']})
    except Exception as e:
        logger.error(f"Slack OAuth error: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "Failed to map Slack integration."})

@slack_app.event("app_mention")
async def handle_app_mentions(body: dict, say: callable, logger: logging.Logger) -> None: # type: ignore
    event = body.get("event", {})
    if "team" not in event:
        event["team"] = body.get("team_id")
    # Since we need a new DB session and background processing,
    # we'll offload the heavy lifting to our own async worker to avoid any timeout issues.
    asyncio.create_task(process_slack_message(event))


@slack_app.event("member_joined_channel")
async def handle_member_joined_channel(event: dict, body: dict, logger: logging.Logger, context: dict = None) -> None: # type: ignore
    logger.info(f"member_joined_channel event received: {event}")
    joined_user = event.get("user")
    
    # Try to find the bot user ID from authorizations or context
    bot_user_id = None
    authorizations = body.get("authorizations")
    if authorizations and isinstance(authorizations, list) and len(authorizations) > 0:
        bot_user_id = authorizations[0].get("user_id")
    
    if not bot_user_id and context:
        bot_user_id = context.get("bot_user_id")
        
    # Only proceed if the joining user is the bot itself
    if bot_user_id and joined_user != bot_user_id:
        return
        
    team_id = event.get("team") or body.get("team_id")
    if not team_id:
        logger.warning("member_joined_channel event missing team_id")
        return
        
    # Since we need a new DB session and background processing,
    # we'll offload the welcome check to a background task to avoid timeout issues.
    asyncio.create_task(_background_member_joined_handler(team_id))


@slack_app.event(re.compile(".*"))
async def log_all_events(event: dict, logger: logging.Logger) -> None: # type: ignore
    logger.info(f"Slack event received: {event.get('type', 'unknown')}")

@slack_app.event("message")
async def handle_message_events(body: dict, say: callable, logger: logging.Logger) -> None: # type: ignore
    event = body.get("event", {})
    # Ignore bot messages to prevent infinite loops
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return
        
    channel = event.get("channel", "")
    channel_type = event.get("channel_type")
    
    # Process only Direct Messages (IMs)
    if channel_type == "im" or channel.startswith("D"):
        if "team" not in event:
            event["team"] = body.get("team_id")
        asyncio.create_task(process_slack_message(event))

@router.post("/events")
@router.post("/events/")
async def slack_events(request: Request) -> Response:
    """Handle incoming Slack events via Bolt."""
    body = await request.body()
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Slack raw body: {body[:500]}")
    return await slack_handler.handle(request)

@router.post("/trigger_monthly_report")
async def trigger_monthly_report(
    tenant_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Diagnostic endpoint to trigger the end-of-month AI generation
    for a specific tenant without waiting for the CRON schedule.
    Requires authentication.
    """
    from backend.app.services.monthly_report import run_monthly_reports
    import asyncio
    
    # Run heavily in background so the request doesn't timeout hitting Claude
    asyncio.create_task(run_monthly_reports(tenant_id))
    return {"status": "dispatched", "message": f"Monthly report requested for Tenant ID {tenant_id}"}

@router.delete("/disconnect")
async def disconnect_slack(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Disconnect Slack by clearing slack_team_id and slack_channel_id."""
    stmt = select(Tenant).where(Tenant.clerk_org_id == user["org_id"])
    res = await session.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
        
    tenant.slack_team_id = None
    tenant.slack_channel_id = None
    session.add(tenant)
    await session.commit()
    return {"status": "disconnected"}

