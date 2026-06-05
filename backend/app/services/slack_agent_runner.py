from backend.app.config import settings
import logging
import uuid
import re
from datetime import datetime, timezone, timedelta
from sqlmodel import select
from backend.app.utils import utc_now
from backend.app.tools.qbo_parser import parse_financial_summary
from backend.app.models.financial_snapshot import FinancialSnapshot
from backend.app.database import _get_engine
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.app.models.slack_message import SlackMessage, SlackUserMap
from backend.app.models.agent_run import AgentRun
from backend.app.integrations.slack import SlackClient
from backend.app.integrations.quickbooks import TokenExpiredError, IntegrationError
from backend.app.agent.graph import app as agent_app

logger = logging.getLogger(__name__)

STALE_DATA_THRESHOLD = timedelta(hours=48)


async def _check_qbo_data_freshness(tenant_id: str, session) -> tuple[str | None, bool]:
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
            f"🔌 Your QuickBooks connection has expired. Please reconnect via the Flowytics dashboard: {settings.FRONTEND_URL}/onboarding/accounting",
            True,
        )

    if integration.last_synced_at is None:
        return (
            "⏳ QuickBooks is connected but no data has been synced yet. A sync may be in progress — please try again in a few minutes.",
            True,
        )

    last_synced = integration.last_synced_at
    if last_synced.tzinfo is not None:
        age = datetime.now(timezone.utc) - last_synced
    else:
        age = utc_now() - last_synced
    if age > STALE_DATA_THRESHOLD:
        days_ago = age.days
        hours_ago = int(age.total_seconds() // 3600)
        time_label = f"{days_ago} days" if days_ago > 0 else f"{hours_ago} hours"
        return (
            f"⚠️ Financial data was last synced {time_label} ago. Numbers may be outdated. "
            f"Trigger a fresh sync with `/sync` or reconnect QuickBooks if needed.",
            False,
        )

    return None, False


async def process_slack_message(event: dict):
    team_id = event.get("team")
    user_id = event.get("user")
    channel = event.get("channel")
    text = event.get("text", "")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts", ts)

    clean_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()

    if not clean_text:
        return

    client = SlackClient()

    _, session_factory = _get_engine()
    async with session_factory() as session:
        stmt = select(Tenant).where(Tenant.slack_team_id == team_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            logger.warning(
                "Message from unknown Slack team",
                extra={"event": "unknown_team", "service": "slack_agent", "org_id": team_id},
            )
            await client.send_reply(channel, thread_ts, "I am not connected to a Flowytics account. Please complete onboarding first.")
            return

        user_map_stmt = select(SlackUserMap).where(SlackUserMap.slack_user_id == user_id)
        u_res = await session.execute(user_map_stmt)
        slack_map = u_res.scalar_one_or_none()

        if not slack_map:
            slack_map = SlackUserMap(
                tenant_id=tenant.id,
                slack_user_id=user_id,
                slack_team_id=team_id
            )
            session.add(slack_map)

        agent_run = AgentRun(
            tenant_id=tenant.id,
            trigger_type="slack_message",
            query=clean_text,
            is_successful=False
        )
        session.add(agent_run)

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

        warning_msg, should_block = await _check_qbo_data_freshness(tenant.id, session)

        if should_block:
            error_blocks = client.format_error_block(
                title="Cannot Process Request",
                message=warning_msg,
                cta=f"<{settings.FRONTEND_URL}/onboarding/accounting|Connect QuickBooks>",
            )
            await client.send_reply(channel, thread_ts, warning_msg, blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.error_message = warning_msg
            await session.commit()
            return

        import time
        start_time = time.perf_counter()
        try:
            # Fetch QBO snapshots and build financial summary
            pl_stmt = select(FinancialSnapshot).where(
                FinancialSnapshot.tenant_id == tenant.id,
                FinancialSnapshot.data_type == "profit_loss"
            ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
            pl_snap = (await session.execute(pl_stmt)).scalar_one_or_none()

            bs_stmt = select(FinancialSnapshot).where(
                FinancialSnapshot.tenant_id == tenant.id,
                FinancialSnapshot.data_type == "balance_sheet"
            ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
            bs_snap = (await session.execute(bs_stmt)).scalar_one_or_none()

            financial_summary = None
            if pl_snap and bs_snap:
                financial_summary = parse_financial_summary(
                    pl_snap.raw_data,
                    bs_snap.raw_data,
                    pl_snap.period_end
                )

            inputs = {
                "messages": [("user", clean_text)],
                "financial_summary": financial_summary
            }
            result = await agent_app.ainvoke(inputs)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # extract tools called
            tools_called = []
            for msg in result.get("messages", []):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        t_name = tc.get("name")
                        if t_name and t_name not in tools_called:
                            tools_called.append(t_name)

            model_used = result.get("recommended_model") or "claude-sonnet-4-6"

            final_message = result["messages"][-1].content

            response_blocks = []

            if warning_msg:
                response_blocks.extend(client.format_stale_data_warning_block(warning_msg))

            response_blocks.extend(client.format_cfo_response_block(final_message))

            fallback = f"{warning_msg}\n\n{final_message}" if warning_msg else final_message

            await client.send_reply(channel, thread_ts, text=fallback, blocks=response_blocks)

            out_msg = SlackMessage(
                tenant_id=tenant.id,
                slack_team_id=team_id,
                slack_channel_id=channel,
                slack_thread_ts=thread_ts,
                slack_user_id=None,
                slack_ts=None,
                direction="outbound",
                content=final_message,
                is_bot=True,
                agent_run_id=agent_run.id
            )
            session.add(out_msg)

            agent_run.is_successful = True
            agent_run.status = "completed"
            agent_run.response = final_message
            agent_run.tools_called = tools_called
            agent_run.model_used = model_used
            agent_run.duration_ms = duration_ms
            await session.commit()

        except (TokenExpiredError, IntegrationError) as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                "QBO integration error during agent invocation",
                extra={"tenant_id": tenant.id, "error_type": type(e).__name__, "provider": "quickbooks"},
                exc_info=True,
            )
            error_blocks = client.format_error_block(
                title="QuickBooks Connection Problem",
                message=f"*Details:* {str(e)}",
                cta=f"<{settings.FRONTEND_URL}/onboarding/accounting|Reconnect QuickBooks>",
            )
            error_text = f"⚠️ QuickBooks connection error: {str(e)}"
            await client.send_reply(channel, thread_ts, error_text, blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.status = "failed"
            agent_run.error_message = str(e)
            agent_run.duration_ms = duration_ms
            await session.commit()

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                "Agent invocation failed",
                extra={"tenant_id": tenant.id, "error_type": type(e).__name__, "service": "langgraph"},
                exc_info=True,
            )
            error_blocks = client.format_error_block(
                title="Processing Error",
                message="I encountered an error processing your request. Please try again later.",
            )
            await client.send_reply(channel, thread_ts, "Processing error — please try again.", blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.status = "failed"
            agent_run.error_message = str(e)
            agent_run.duration_ms = duration_ms
            await session.commit()