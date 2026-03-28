import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError

from backend.app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize the Bolt AsyncApp
slack_app = AsyncApp(
    token=settings.SLACK_BOT_TOKEN or "xoxb-dummy-token",
    signing_secret=settings.SLACK_SIGNING_SECRET or "dummy-secret"
)

# ── Block Kit Constants ─────────────────────────────────────────
_MAX_BLOCK_TEXT = 2900  # Slack cap is 3000; leave margin for formatting
_BRAND_FOOTER = "🤖 _Flowytics AI CFO — powered by your real QuickBooks data_"

_RUNWAY_BADGES = {
    "critical": "🔴 Critical",
    "warning": "🟡 Warning",
    "monitor": "🟠 Monitor",
    "healthy": "🟢 Healthy",
}

_TREND_ARROWS = {
    "increasing": "📈 Increasing",
    "stable": "➡️ Stable",
    "decreasing": "📉 Decreasing",
}


def _fmt_currency(value, fallback: str = "N/A") -> str:
    """Format a Decimal/int/float as $XX,XXX with sign."""
    if value is None:
        return fallback
    try:
        v = Decimal(str(value))
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(v):,.0f}"
    except Exception:
        return fallback


def _fmt_pct(value, fallback: str = "N/A") -> str:
    """Format a Decimal/int/float as XX.X%."""
    if value is None:
        return fallback
    try:
        return f"{Decimal(str(value)):,.1f}%"
    except Exception:
        return fallback


def _timestamp_str() -> str:
    return datetime.now(timezone.utc).strftime("%b %d, %Y at %H:%M UTC")


def _split_into_sections(text: str) -> list[str]:
    """
    Split long text into chunks that fit within Slack's 3000-char block limit.
    Splits on paragraph boundaries (double newline) when possible.
    """
    if len(text) <= _MAX_BLOCK_TEXT:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= _MAX_BLOCK_TEXT:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If a single paragraph exceeds limit, hard-split it
            if len(para) > _MAX_BLOCK_TEXT:
                for i in range(0, len(para), _MAX_BLOCK_TEXT):
                    chunks.append(para[i:i + _MAX_BLOCK_TEXT])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


class SlackClient:
    """Slack Bot API client for sending messages and handling conversations."""

    def __init__(self) -> None:
        self.client = slack_app.client

    async def send_message(self, channel: str, text: str, blocks: list = None) -> bool:
        """Send a message to a Slack channel or DM."""
        try:
            await self.client.chat_postMessage(channel=channel, text=text, blocks=blocks)
            return True
        except SlackApiError as e:
            logger.error(
                "Error sending Slack message",
                extra={"event": "slack_send_failed", "error_type": e.response["error"]},
            )
            return False

    async def send_reply(self, channel: str, thread_ts: str, text: str, blocks: list = None) -> bool:
        """Reply in a Slack thread."""
        try:
            await self.client.chat_postMessage(
                channel=channel, thread_ts=thread_ts, text=text, blocks=blocks
            )
            return True
        except SlackApiError as e:
            logger.error(
                "Error sending Slack reply",
                extra={"event": "slack_reply_failed", "error_type": e.response["error"]},
            )
            return False

    # ── CFO Response Formatting ─────────────────────────────────

    def format_cfo_response_block(self, text: str) -> list:
        """
        Format the AI CFO answer in rich Block Kit.
        Handles long responses by splitting into multiple section blocks,
        and adds a branded footer.
        """
        blocks = []

        # Header bar
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "💼 AI CFO Analysis",
                "emoji": True,
            },
        })

        # Content sections (auto-split for length)
        sections = _split_into_sections(text)
        for section_text in sections:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": section_text},
            })

        # Divider + branded footer with timestamp
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": _BRAND_FOOTER},
                {"type": "mrkdwn", "text": f"📅 _{_timestamp_str()}_"},
            ],
        })

        return blocks

    # ── Proactive Alert Formatting ──────────────────────────────

    def format_proactive_alert_block(self, alert_text: str, severity: str = "warning") -> list:
        """
        Format a proactive financial alert with urgency framing.
        Includes header, severity badge, alert body, and an action CTA.
        """
        emoji = "🚨" if severity == "critical" else "⚠️"
        severity_label = "CRITICAL" if severity == "critical" else "WARNING"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Financial Alert — {severity_label}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": alert_text},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "💡 *What to do next:*\n"
                        "• Ask me: _\"What's my current burn rate?\"_\n"
                        "• Ask me: _\"What if I cut cloud costs by 30%?\"_\n"
                        "• Review your <http://localhost:3000/dashboard|Flowytics Dashboard>"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": _BRAND_FOOTER},
                    {"type": "mrkdwn", "text": f"🕐 _{_timestamp_str()}_"},
                ],
            },
        ]

        return blocks

    # ── Monthly CFO Report ──────────────────────────────────────

    def format_monthly_cfo_report_block(
        self,
        metrics: dict,
        executive_summary: str,
        key_consideration: str,
        tenant_name: str = "Your Startup",
    ) -> list:
        """
        Premium end-of-month CFO report with KPI dashboard, executive summary,
        and actionable recommendation.
        """
        mrr = metrics.get("mrr")
        mrr_growth = metrics.get("mrr_growth")
        net_burn = metrics.get("net_burn")
        runway_months = metrics.get("runway_months")
        cash_balance = metrics.get("cash_balance")

        # Compute runway status badge
        try:
            rm = Decimal(str(runway_months)) if runway_months is not None else Decimal("9999")
            if rm < 3:
                status_badge = _RUNWAY_BADGES["critical"]
            elif rm < 6:
                status_badge = _RUNWAY_BADGES["warning"]
            elif rm < 12:
                status_badge = _RUNWAY_BADGES["monitor"]
            else:
                status_badge = _RUNWAY_BADGES["healthy"]
        except Exception:
            status_badge = "⚪ Unknown"

        # Growth arrow indicator
        try:
            g = Decimal(str(mrr_growth)) if mrr_growth is not None else Decimal("0")
            growth_indicator = "📈" if g > 0 else ("📉" if g < 0 else "➡️")
        except Exception:
            growth_indicator = "➡️"

        blocks = [
            # ── Report Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 Monthly CFO Report — {tenant_name}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            # ── Executive Summary
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive Summary*\n{executive_summary}",
                },
            },
            {"type": "divider"},
            # ── KPI Dashboard (2×2 grid)
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📋 *Key Performance Indicators*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*💰 Cash Balance*\n{_fmt_currency(cash_balance)}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*🔥 Net Burn*\n{_fmt_currency(net_burn)}/mo",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*⏳ Runway*\n{runway_months} months\n{status_badge}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*{growth_indicator} MRR*\n"
                            f"{_fmt_currency(mrr)} ({_fmt_pct(mrr_growth)})"
                        ),
                    },
                ],
            },
            {"type": "divider"},
            # ── Key Consideration
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🎯 *Key Consideration*\n{key_consideration}",
                },
            },
            {"type": "divider"},
            # ── Quick Actions
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "💬 *Dive deeper — ask me:*\n"
                        "• _\"Break down my expenses by category\"_\n"
                        "• _\"What if I raise a $500K round?\"_\n"
                        "• _\"Are there any spending anomalies?\"_"
                    ),
                },
            },
            # ── Footer
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": _BRAND_FOOTER},
                    {"type": "mrkdwn", "text": f"📅 _{_timestamp_str()}_"},
                ],
            },
        ]

        return blocks

    # ── Error / Warning Blocks ──────────────────────────────────

    def format_error_block(self, title: str, message: str, cta: str | None = None) -> list:
        """
        Standardized error message block for integration failures,
        disconnects, and user-facing errors.
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"❌ {title}",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        if cta:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👉 *Action required:* {cta}",
                },
            })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": _BRAND_FOOTER},
            ],
        })

        return blocks

    def format_stale_data_warning_block(self, warning_text: str) -> list:
        """
        Visual stale-data warning banner that gets prepended to agent responses
        when QBO data is older than the freshness threshold.
        """
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *Data Freshness Warning*\n{warning_text}",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔄 Sync Now", "emoji": True},
                    "url": "http://localhost:3000/dashboard",
                    "action_id": "sync_now_cta",
                },
            },
            {"type": "divider"},
        ]

