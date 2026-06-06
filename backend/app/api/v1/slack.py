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


async def _background_member_joined_handler(team_id: str, channel_id: str):
    """Background task to handle bot joining a channel: find tenant and check welcome message."""
    logger.info(f"_background_member_joined_handler called: team_id={team_id}, channel_id={channel_id}")
    from backend.app.database import _get_engine
    from backend.app.models.tenant import Tenant
    from backend.app.models.integration import Integration
    from backend.app.models.slack_message import SlackUserMap
    from backend.app.services.onboarding_welcome import send_channel_greeting
    
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
                
            await send_channel_greeting(tenant_id, channel_id, session)
            
        except Exception as e:
            logger.error(f"Failed to process member_joined_channel for team {team_id}: {e}")


async def _safe_member_joined_handler(team_id: str, channel_id: str):
    try:
        logger.info(f"_background_member_joined_handler starting: team_id={team_id}, channel_id={channel_id}")
        await _background_member_joined_handler(team_id, channel_id)
        logger.info(f"_background_member_joined_handler completed: team_id={team_id}, channel_id={channel_id}")
    except Exception as e:
        logger.error(f"member_joined_channel handler failed: {e}", exc_info=True)

# Bolt Adapter
slack_handler = AsyncSlackRequestHandler(slack_app)

from slack_sdk.errors import SlackApiError
from starlette.responses import Response

@router.get("/install")
async def slack_install(user: dict = Depends(get_current_user)):
    settings = get_settings()
    client_id = settings.SLACK_CLIENT_ID
    state = jwt.encode(
        {"org_id": user["org_id"], "clerk_user_id": user["user_id"]},
        settings.CLERK_SECRET_KEY[:32],
        algorithm="HS256"
    )
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
        clerk_user_id = payload.get("clerk_user_id")
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
        team_id = response.get("team", {}).get("id")  # type: ignore
        incoming_webhook = response.get("incoming_webhook") or {}  # type: ignore
        channel_id = incoming_webhook.get("channel_id")  # type: ignore
        
        # We don't save the bot token currently (assuming single global workspace for MVP)
        # We just map the team_id to the tenant
        stmt = select(Tenant).where(Tenant.clerk_org_id == org_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if tenant:
            tenant.slack_team_id = team_id
            if channel_id:
                tenant.slack_channel_id = channel_id
            session.add(tenant)
            await session.commit()
            
            # Map authorizing Slack user to Clerk user ID
            authed_user_id = response.get("authed_user", {}).get("id")  # type: ignore
            if authed_user_id and clerk_user_id:
                from backend.app.models.slack_message import SlackUserMap
                map_stmt = select(SlackUserMap).where(SlackUserMap.slack_user_id == authed_user_id)
                map_res = await session.execute(map_stmt)
                slack_map = map_res.scalar_one_or_none()
                if slack_map:
                    slack_map.clerk_user_id = clerk_user_id
                    slack_map.tenant_id = tenant.id
                    session.add(slack_map)
                else:
                    slack_map = SlackUserMap(
                        tenant_id=tenant.id,
                        clerk_user_id=clerk_user_id,
                        slack_user_id=authed_user_id,
                        slack_team_id=team_id  # type: ignore
                    )
                    session.add(slack_map)
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




@slack_app.event(re.compile(".*"))
async def log_all_events(event: dict, logger: logging.Logger) -> None: # type: ignore
    logger.info(f"Slack event received: {event.get('type', 'unknown')}")

@slack_app.event("message")
async def handle_message_events(body: dict, say: callable, logger: logging.Logger) -> None: # type: ignore
    event = body.get("event", {})
    # Ignore bot messages to prevent infinite loops
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return
        
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
    
    import json
    try:
        body_dict = json.loads(body)
        event = body_dict.get("event", {})
        if event.get("type") == "member_joined_channel":
            team_id = body_dict.get("team_id") or event.get("team")
            channel_id = event.get("channel")
            bot_user_id = os.getenv("SLACK_BOT_USER_ID")
            logger.info(f"member_joined_channel check: event_user={event.get('user')}, bot_user_id={bot_user_id}")
            if bot_user_id and event.get("user") == bot_user_id:
                asyncio.create_task(_safe_member_joined_handler(team_id, channel_id))
    except Exception as e:
        logger.debug(f"Could not parse request body as JSON for manual event dispatch: {e}")
        
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

