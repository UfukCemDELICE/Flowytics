import logging
import uuid
import re
from sqlmodel import select

from backend.app.database import _get_engine
from backend.app.models.tenant import Tenant
from backend.app.models.slack_message import SlackMessage, SlackUserMap
from backend.app.models.agent_run import AgentRun
from backend.app.integrations.slack import SlackClient
from backend.app.agent.graph import app as agent_app

logger = logging.getLogger(__name__)

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
        
        try:
            # Call the agent
            inputs = {"messages": [("user", clean_text)]}
            # LangGraph currently doesn't natively support full async easily without async tools,
            # but we can call it in an executor, or just `ainvoke` if agent tools are async or support it.
            # Fast/Simple: we use ainvoke
            result = await agent_app.ainvoke(inputs)
            
            final_message = result["messages"][-1].content
            
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
            
        except Exception as e:
            logger.error(f"Agent failed for tenant {tenant.id}: {str(e)}", exc_info=True)
            await client.send_reply(channel, thread_ts, "I encountered an error processing your request. Please try again later.")
            agent_run.error_message = str(e)
            await session.commit()
