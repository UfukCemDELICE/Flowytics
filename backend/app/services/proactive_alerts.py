import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlmodel import select
from backend.app.utils import utc_now, clean_unicode_minus

from backend.app.database import _get_engine
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.app.models.financial_snapshot import FinancialSnapshot
from backend.app.integrations.slack import SlackClient

from backend.app.tools.qbo_parser import parse_financial_summary
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.anomaly import calculate_anomalies

logger = logging.getLogger(__name__)

STALE_DATA_THRESHOLD = timedelta(hours=48)

async def run_proactive_alerts():
    """
    Scheduled job that checks all active tenants for financial exceptions:
    1. Runway under 4 months.
    2. Burn Rate MoM increase > 25%.
    3. Critical Expense Anomalies.
    If triggered, pushes a Block Kit alert to the mapped Slack channel.
    """
    logger.info("Starting scheduled proactive alerts job.")
    client = SlackClient()
    
    _, session_factory = _get_engine()
    async with session_factory() as session:
        # Fetch tenants who have a slack_channel_id configured (or team_id)
        stmt = select(Tenant).where(Tenant.slack_team_id != None)
        result = await session.execute(stmt)
        tenants = result.scalars().all()
        
        for tenant in tenants:
            try:
                # ── Data freshness gate ─────────────────────────
                integ_stmt = select(Integration).where(
                    Integration.tenant_id == tenant.id,
                    Integration.provider == "quickbooks",
                )
                integ_res = await session.execute(integ_stmt)
                integration = integ_res.scalar_one_or_none()

                if not integration or integration.sync_status == "disconnected":
                    channel = tenant.slack_channel_id or "#general"
                    blocks = client.format_proactive_alert_block(
                        "🔌 Your QuickBooks connection is disconnected. "
                        "Please reconnect via the Flowytics dashboard to resume financial monitoring.",
                        severity="critical",
                    )
                    await client.send_message(channel, "QuickBooks disconnected", blocks=blocks)
                    logger.warning(f"Skipping tenant {tenant.id}: QBO disconnected")
                    continue

                if integration.last_synced_at:
                    last_synced = integration.last_synced_at
                    if last_synced.tzinfo is not None:
                        age = datetime.now(timezone.utc) - last_synced
                    else:
                        age = utc_now() - last_synced
                    if age > STALE_DATA_THRESHOLD:
                        channel = tenant.slack_channel_id or "#general"
                        days_ago = age.days
                        blocks = client.format_proactive_alert_block(
                            f"⚠️ Financial data is {days_ago} day(s) old. "
                            f"Proactive analysis is paused until fresh data is available. "
                            f"Please trigger a sync or reconnect QuickBooks.",
                            severity="warning",
                        )
                        await client.send_message(channel, "Stale financial data", blocks=blocks)
                        logger.info(f"Skipping tenant {tenant.id}: data stale ({days_ago}d)")
                        continue
                # ────────────────────────────────────────────────

                # 1. Fetch latest P&L and Balance Sheet
                pl_stmt = select(FinancialSnapshot).where(
                    FinancialSnapshot.tenant_id == tenant.id,
                    FinancialSnapshot.data_type == "profit_loss"
                ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)
                bs_stmt = select(FinancialSnapshot).where(
                    FinancialSnapshot.tenant_id == tenant.id,
                    FinancialSnapshot.data_type == "balance_sheet"
                ).order_by(FinancialSnapshot.snapshot_date.desc()).limit(1)

                pl_res = await session.execute(pl_stmt)
                bs_res = await session.execute(bs_stmt)
                pl_snap = pl_res.scalar_one_or_none()
                bs_snap = bs_res.scalar_one_or_none()
                
                if not pl_snap or not bs_snap:
                    # Skip if missing necessary snapshots
                    logger.debug(f"Skipping {tenant.id}: missing snapshots")
                    continue
                
                # Setup summary
                summary = parse_financial_summary(
                    pl_snap.raw_data,
                    bs_snap.raw_data,
                    pl_snap.period_end or pl_snap.snapshot_date
                )
                
                # Check for insufficient history
                if not summary.monthly_financials:
                    continue
                
                # 2. Run Tools
                burn = calculate_burn_rate.invoke({"summary": summary})
                runway = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
                anomalies = calculate_anomalies.invoke({"summary": summary})
                
                alerts = []
                
                # Rule A: Runway < 4 months
                if runway.runway_months < Decimal("4.0"):
                    alerts.append(f"• *Critical Runway:* You only have {runway.runway_months} months of cash remaining at current burn.")
                    
                # Rule B: Burn Rate increase > 25%
                if len(summary.monthly_financials) >= 2:
                    current_burn = burn.net_burn_monthly
                    # Re-calculate to find previous burn (simplify for MVP: just read from monthly totals)
                    prev_month = summary.monthly_financials[-2]
                    prev_burn = prev_month.total_expenses - prev_month.total_revenue
                    if prev_burn > Decimal("0") and current_burn > prev_burn:
                        increase_pct = (current_burn - prev_burn) / prev_burn * Decimal("100")
                        if increase_pct > Decimal("25.0"):
                            alerts.append(f"• *Spiking Burn Rate:* Your Net Burn increased by {increase_pct.quantize(Decimal('0.0'))}% this month.")
                
                # Rule C: Anomalies Detected
                for anomaly in anomalies.anomalies:
                    if anomaly.severity == "critical":
                        alerts.append(f"• *Critical Anomaly:* {anomaly.description}")

                # 3. Dispatch Alert if necessary
                if alerts:
                    # Prefer using a specific configured channel or fall back to sending it globally if unconfigured 
                    # Defaulting to an alert placeholder if channel is mostly omitted in MVP
                    channel = tenant.slack_channel_id or "#general"
                    
                    alert_text = "The CFO AI has detected the following critical financial conditions:\n" + "\n".join(alerts)
                    alert_text = clean_unicode_minus(alert_text)
                    blocks = client.format_proactive_alert_block(alert_text, severity="critical")
                    
                    # For demo / early MVP, just try logging if we don't have the exact channel hook.
                    # Send to the team's designated channel
                    success = await client.send_message(channel, alert_text, blocks=blocks)
                    if success:
                        logger.info(f"Published proactive alert to tenant {tenant.id}")
                    else:
                        logger.warning(f"Failed to publish alert to {tenant.id} via channel {channel}")
            
            except Exception as e:
                logger.error(f"Error checking proactive alerts for tenant {tenant.id}: {e}")
