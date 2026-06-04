"""
Onboarding welcome message service.

Sends a rich Slack Block Kit welcome message when a tenant completes
the critical onboarding milestones: QuickBooks synced + Slack connected.

Designed to be called from multiple trigger points (QBO first-sync callback,
Slack OAuth callback) — it is idempotent via the `onboarding_completed` flag
on the Tenant model, guaranteeing exactly-once delivery.
"""

import logging
from uuid import UUID
from sqlmodel import select

from backend.app.database import _get_engine
from backend.app.models.tenant import Tenant
from backend.app.models.integration import Integration
from backend.app.integrations.slack import SlackClient

logger = logging.getLogger(__name__)


async def send_welcome_message_if_ready(tenant_id: str | UUID, session=None) -> bool:
    """
    Check if the tenant has completed QBO + Slack onboarding, and if so,
    send a one-time welcome message. Returns True if the message was sent.

    Args:
        tenant_id: The tenant's internal UUID (str or UUID object).
        session: Optional async DB session. If None, creates one internally.

    Returns:
        True if welcome was sent, False if conditions weren't met or already sent.
    """
    owns_session = session is None
    if owns_session:
        _, session_factory = _get_engine()
        session = session_factory()
        await session.__aenter__()

    try:
        return await _check_and_send(tenant_id, session)
    except Exception as e:
        logger.error(f"Welcome message failed for tenant {tenant_id}: {e}")
        return False
    finally:
        if owns_session:
            await session.__aexit__(None, None, None)


async def _check_and_send(tenant_id: str | UUID, session) -> bool:
    """Core logic: verify milestones met, send welcome, mark complete."""

    # 1. Load tenant — using internal UUID only
    tenant_uuid: UUID | str
    if isinstance(tenant_id, UUID):
        tenant_uuid = tenant_id
    else:
        try:
            tenant_uuid = UUID(str(tenant_id))
        except ValueError:
            tenant_uuid = tenant_id

    stmt = select(Tenant).where(Tenant.id == tenant_uuid)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning(f"Welcome check: tenant not found for ID {tenant_id}")
        return False

    # 2. Idempotency gate — already sent
    if tenant.onboarding_completed:
        logger.debug(f"Welcome already sent for tenant {tenant.id}")
        return False

    # 3. Check milestone: Slack connected
    if not tenant.slack_team_id:
        logger.debug(f"Welcome deferred: Slack not yet connected for tenant {tenant.id}")
        return False

    # 4. Check milestone: QuickBooks synced (at least one successful sync)
    integ_stmt = select(Integration).where(
        Integration.tenant_id == tenant.id,
        Integration.provider == "quickbooks",
        Integration.last_synced_at != None,
    )
    integ_result = await session.execute(integ_stmt)
    integration = integ_result.scalar_one_or_none()

    if not integration:
        logger.debug(f"Welcome deferred: QBO not yet synced for tenant {tenant.id}")
        return False

    # 5. All milestones met — send welcome
    channel = tenant.slack_channel_id or "#general"
    client = SlackClient()
    blocks = _build_welcome_blocks(tenant.name)
    fallback_text = "✅ Flowytics is connected! Your AI CFO is ready. Your first financial report will arrive within 24 hours."

    success = await client.send_message(channel, fallback_text, blocks=blocks)

    if success:
        # 6. Mark onboarding complete — prevents duplicate sends
        tenant.onboarding_completed = True
        session.add(tenant)
        await session.commit()
        logger.info(f"Welcome message sent to tenant {tenant.id} on channel {channel}")
        return True
    else:
        logger.warning(f"Welcome Slack delivery failed for tenant {tenant.id}")
        return False


def _build_welcome_blocks(company_name: str) -> list:
    """Build a premium Slack Block Kit welcome message."""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "✅ Flowytics is connected!",
                "emoji": True,
            },
        },
        {
            "type": "divider",
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Hey *{company_name}* team! 👋\n\nYour AI CFO is ready to go. Here's what happens next:",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "📊 *QuickBooks*\nConnected & syncing",
                },
                {
                    "type": "mrkdwn",
                    "text": "💬 *Slack*\nReady for questions",
                },
                {
                    "type": "mrkdwn",
                    "text": "📈 *First Report*\nWithin 24 hours",
                },
                {
                    "type": "mrkdwn",
                    "text": "🚨 *Proactive Alerts*\nMonitoring daily",
                },
            ],
        },
        {
            "type": "divider",
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": '*Try me now!* Mention me in any channel and ask:\n• _"What\'s my burn rate?"_\n• _"How long is my runway?"_\n• _"What if I hire 2 engineers?"_',
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "🤖 _Flowytics AI CFO — $150/mo of financial intelligence, powered by your real QuickBooks data._",
                },
            ],
        },
    ]
