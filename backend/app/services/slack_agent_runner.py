import logging
import uuid
import re
from datetime import datetime, timezone, timedelta
from sqlmodel import select

from backend.app.database import _get_engine
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.app.models.slack_message import SlackMessage, SlackUserMap
from backend.app.models.agent_run import AgentRun
from backend.app.integrations.slack import SlackClient
from backend.app.integrations.quickbooks import TokenExpiredError, IntegrationError
from backend.app.agent.graph import app as agent_app

logger = logging.getLogger(__name__)

# Stale data threshold: if last sync is older than this, warn the user.
STALE_DATA_THRESHOLD = timedelta(hours=48)


async def _check_qbo_data_freshness(tenant_id: str, session) -> tuple[str | None, bool]:
    """
    Check the QBO integration status and data freshness for a tenant.
    
    Returns:
        (warning_message, should_block):
            - warning_message: A text banner to prepend, or None if data is fresh.
            - should_block: If True, the agent should NOT be invoked at all.
    """
    stmt = select(Integration).where(
        Integration.tenant_id == tenant_id,
        Integration.provider == "quickbooks",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        return (
            "⚠️ No QuickBooks account connected. Please connect QuickBooks via the Flowytics dashboard to get financial insights.",
            True,
        )

    if integration.sync_status == "disconnected":
        return (
            "🔌 Your QuickBooks connection has expired. Please reconnect via the Flowytics dashboard: http://localhost:3000/onboarding/accounting",
            True,
        )

    if integration.last_synced_at is None:
        return (
            "⏳ QuickBooks is connected but no data has been synced yet. A sync may be in progress — please try again in a few minutes.",
            True,
        )

    age = datetime.now(timezone.utc) - integration.last_synced_at
    if age > STALE_DATA_THRESHOLD:
        days_ago = age.days
        hours_ago = int(age.total_seconds() // 3600)
        time_label = f"{days_ago} days" if days_ago > 0 else f"{hours_ago} hours"
        return (
            f"⚠️ Financial data was last synced {time_label} ago. Numbers may be outdated. "
            f"Trigger a fresh sync with `/sync` or reconnect QuickBooks if needed.",
            False,  # Warn but still allow the agent to respond
        )

    return None, False


async def process_slack_message(event: dict):
    """
    Background worker that receives the Slack event, finds the user mapping,
    invokes the LangGraph agent, and sends the response back to Slack.
    """
    team_id = event.get("team")
    user_id = event.get("user")
    channel = event.get("channel")
    text = event.get("text", "")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts", ts)  # Reply in thread if already in one, else start thread
    
    # Strip out the bot mention (e.g., <@U06XXXXXX>)
    clean_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
    
    if not clean_text:
        return
        
    client = SlackClient()
    
    _, session_factory = _get_engine()
    async with session_factory() as session:
        # Find Tenant by checking the team_id map
        stmt = select(Tenant).where(Tenant.slack_team_id == team_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            logger.warning(f"Message from unknown team_id {team_id}")
            await client.send_reply(channel, thread_ts, "I am not connected to a Flowytics account. Please complete onboarding first.")
            return

        # Simple Auto-mapping for users.
        # In a real setup, we might force authorization via OAuth for each user.
        user_map_stmt = select(SlackUserMap).where(SlackUserMap.slack_user_id == user_id)
        u_res = await session.execute(user_map_stmt)
        slack_map = u_res.scalar_one_or_none()
        
        if not slack_map:
            # Auto-register
            slack_map = SlackUserMap(slack_user_id=user_id, slack_team_id=team_id)
            session.add(slack_map)
        
        # Create an Agent Run Log
        run_id = str(uuid.uuid4())
        agent_run = AgentRun(
            tenant_id=tenant.id,
            trigger_type="slack_message",
            query=clean_text,
            is_successful=False
        )
        session.add(agent_run)
        
        # Log user inbound message
        in_msg = SlackMessage(
            tenant_id=tenant.id,
            slack_team_id=team_id,
            slack_channel_id=channel,
            slack_thread_ts=thread_ts,
            slack_user_id=user_id,
            slack_ts=ts,
            direction="inbound",
            content=text,
            is_bot=False,
            agent_run_id=agent_run.id
        )
        session.add(in_msg)
        await session.commit()
        await session.refresh(agent_run)
        
        # ── Data freshness gate ──────────────────────────────────
        warning_msg, should_block = await _check_qbo_data_freshness(tenant.id, session)
        
        if should_block:
            # Integration is missing or broken — don't call the agent at all
            await client.send_reply(channel, thread_ts, warning_msg)
            agent_run.is_successful = False
            agent_run.error_message = warning_msg
            await session.commit()
            return
        # ─────────────────────────────────────────────────────────
        
        try:
            # Call the agent
            inputs = {"messages": [("user", clean_text)]}
            result = await agent_app.ainvoke(inputs)
            
            final_message = result["messages"][-1].content
            
            # Prepend stale data warning if applicable
            if warning_msg:
                final_message = f"{warning_msg}\n\n---\n\n{final_message}"
            
            # Send message back to slack
            blocks = client.format_cfo_response_block(final_message)
            await client.send_reply(channel, thread_ts, text=final_message, blocks=blocks)
            
            # Log bot response
            out_msg = SlackMessage(
                tenant_id=tenant.id,
                slack_team_id=team_id,
                slack_channel_id=channel,
                slack_thread_ts=thread_ts,
                slack_user_id=None,
                slack_ts=None, # In reality we'd grab the outbound message ts from the API response
                direction="outbound",
                content=final_message,
                is_bot=True,
                agent_run_id=agent_run.id
            )
            session.add(out_msg)
            
            agent_run.is_successful = True
            agent_run.response = final_message
            await session.commit()

        except (TokenExpiredError, IntegrationError) as e:
            logger.error(f"QBO integration error for tenant {tenant.id}: {str(e)}", exc_info=True)
            error_reply = (
                "⚠️ There's a problem with your QuickBooks connection.\n\n"
                f"*Details:* {str(e)}\n\n"
                "Please reconnect QuickBooks via the Flowytics dashboard: "
                "http://localhost:3000/onboarding/accounting"
            )
            await client.send_reply(channel, thread_ts, error_reply)
            agent_run.error_message = str(e)
            await session.commit()

        except Exception as e:
            logger.error(f"Agent failed for tenant {tenant.id}: {str(e)}", exc_info=True)
            await client.send_reply(channel, thread_ts, "I encountered an error processing your request. Please try again later.")
            agent_run.error_message = str(e)
            await session.commit()
