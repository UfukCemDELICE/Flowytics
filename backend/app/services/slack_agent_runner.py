from backend.app.config import settings
import logging
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
from backend.app.utils import clean_unicode_minus

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
        # Check for duplicate processing (dedup by channel and ts)
        if channel and ts:
            dup_stmt = select(SlackMessage).where(
                SlackMessage.slack_channel_id == channel,
                SlackMessage.slack_ts == ts,
                SlackMessage.direction == "inbound"
            )
            dup_res = await session.execute(dup_stmt)
            if dup_res.scalar_one_or_none() is not None:
                logger.info(
                    "Duplicate Slack message detected via early query, ignoring",
                    extra={"channel": channel, "ts": ts}
                )
                return

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
        
        from sqlalchemy.exc import IntegrityError
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.info(
                "Duplicate Slack message caught by unique constraint, aborting",
                extra={"channel": channel, "ts": ts}
            )
            return

        await session.refresh(agent_run)

        # Part A — Load conversation history
        is_threaded = event.get("thread_ts") is not None and event.get("thread_ts") != ts
        if is_threaded:
            history_stmt = (
                select(SlackMessage)
                .where(
                    SlackMessage.tenant_id == tenant.id,
                    SlackMessage.slack_channel_id == channel,
                    SlackMessage.slack_thread_ts == thread_ts,
                    SlackMessage.id != in_msg.id
                )
            )
        else:
            now_val = utc_now()
            from sqlalchemy import or_, and_
            history_stmt = (
                select(SlackMessage)
                .where(
                    SlackMessage.tenant_id == tenant.id,
                    SlackMessage.slack_channel_id == channel,
                    SlackMessage.created_at >= now_val - timedelta(minutes=30),
                    SlackMessage.id != in_msg.id,
                    or_(
                        and_(SlackMessage.direction == "inbound", SlackMessage.slack_user_id == user_id),
                        SlackMessage.direction == "outbound"
                    )
                )
            )

        history_stmt = history_stmt.order_by(SlackMessage.created_at.desc()).limit(6)
        history_res = await session.execute(history_stmt)
        history_rows = history_res.scalars().all()

        # Present chronologically (ascending)
        history_rows.reverse()

        history_tuples = []
        for msg in history_rows:
            content = msg.content or ""
            if msg.direction == "inbound":
                clean_content = re.sub(r'<@[A-Z0-9]+>', '', content).strip()
                history_tuples.append(("user", clean_content))
            elif msg.direction == "outbound":
                history_tuples.append(("assistant", content))

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

        if not pl_snap or not bs_snap:
            error_msg = clean_unicode_minus("Please connect your QuickBooks account first.")
            error_blocks = client.format_error_block(
                title="Connection Required",
                message=error_msg,
                cta=f"<{settings.FRONTEND_URL}/onboarding/accounting|Connect QuickBooks>",
            )
            await client.send_reply(channel, thread_ts, error_msg, blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.status = "failed"
            agent_run.error_message = error_msg
            await session.commit()
            return

        warning_msg, should_block = await _check_qbo_data_freshness(tenant.id, session)
        if warning_msg:
            warning_msg = clean_unicode_minus(warning_msg)

        if should_block:
            error_blocks = client.format_error_block(
                title="Cannot Process Request",
                message=warning_msg,
                cta=f"<{settings.FRONTEND_URL}/onboarding/accounting|Connect QuickBooks>",
            )
            await client.send_reply(channel, thread_ts, warning_msg, blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.status = "failed"
            agent_run.error_message = warning_msg
            await session.commit()
            return

        import time
        start_time = time.perf_counter()
        try:
            # Fetch integration sync status
            integration_stmt = select(Integration).where(
                Integration.tenant_id == tenant.id,
                Integration.provider == "quickbooks"
            )
            integration = (await session.execute(integration_stmt)).scalar_one_or_none()

            financial_summary = parse_financial_summary(
                pl_snap.raw_data,
                bs_snap.raw_data,
                pl_snap.period_end
            )

            inputs = {
                "messages": [*history_tuples, ("user", clean_text)],
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

            if integration and integration.sync_status == "error":
                last_synced_str = "N/A"
                if integration.last_synced_at:
                    last_synced_str = integration.last_synced_at.strftime("%Y-%m-%d")
                sync_warning = f"⚠️ QuickBooks sync is currently unavailable. Showing data from last successful sync on {last_synced_str}."
                final_message = f"{sync_warning}\n\n{final_message}"
                warning_msg = None

            final_message = clean_unicode_minus(final_message)

            response_blocks = []

            if warning_msg:
                response_blocks.extend(client.format_stale_data_warning_block(warning_msg))

            response_blocks.extend(client.format_cfo_response_block(final_message))

            fallback = f"{warning_msg}\n\n{final_message}" if warning_msg else final_message

            outbound_ts = await client.send_reply(channel, thread_ts, text=fallback, blocks=response_blocks)

            out_msg = SlackMessage(
                tenant_id=tenant.id,
                slack_team_id=team_id,
                slack_channel_id=channel,
                slack_thread_ts=thread_ts,
                slack_user_id=None,
                slack_ts=outbound_ts if isinstance(outbound_ts, str) else None,
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
            error_msg_str = clean_unicode_minus(str(e))
            error_blocks = client.format_error_block(
                title="QuickBooks Connection Problem",
                message=f"*Details:* {error_msg_str}",
                cta=f"<{settings.FRONTEND_URL}/onboarding/accounting|Reconnect QuickBooks>",
            )
            error_text = clean_unicode_minus(f"⚠️ QuickBooks connection error: {error_msg_str}")
            await client.send_reply(channel, thread_ts, error_text, blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.status = "failed"
            agent_run.error_message = error_msg_str
            agent_run.duration_ms = duration_ms
            await session.commit()

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                "Agent invocation failed",
                extra={"tenant_id": tenant.id, "error_type": type(e).__name__, "service": "langgraph"},
                exc_info=True,
            )
            error_msg_str = clean_unicode_minus(str(e))
            error_blocks = client.format_error_block(
                title="Processing Error",
                message="I encountered an error processing your request. Please try again later.",
            )
            await client.send_reply(channel, thread_ts, "Processing error — please try again.", blocks=error_blocks)
            agent_run.is_successful = False
            agent_run.status = "failed"
            agent_run.error_message = error_msg_str
            agent_run.duration_ms = duration_ms
            await session.commit()