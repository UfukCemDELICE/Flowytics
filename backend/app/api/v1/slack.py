import hashlib
import hmac
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from supabase import create_client

from backend.app.config import get_settings
from backend.app.integrations.slack import SlackClient

router = APIRouter(prefix="/slack", tags=["slack"])


def _verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature using signing secret."""
    settings = get_settings()
    if abs(time.time() - int(timestamp)) > 300:
        return False  # Replay attack protection
    base_string = f"v0:{timestamp}:{request_body.decode()}"
    expected = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        base_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _handle_message(event: dict, channel: str, thread_ts: str) -> None:
    """Process a Slack message event through the orchestrator and reply."""
    from backend.app.services.financial import FinancialService
    from backend.app.agents.orchestrator import compiled_graph

    settings = get_settings()
    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    svc = FinancialService(db)
    slack = SlackClient()

    slack_user_id = event.get("user", "")
    text = event.get("text", "")

    # Map Slack user to Clerk user
    clerk_user_id = await svc.get_clerk_user_from_slack(slack_user_id)
    if not clerk_user_id:
        await slack.send_reply(
            channel=channel,
            thread_ts=thread_ts,
            text="Your Slack account is not linked to Flowytics. Connect at https://app.flowytics.com",
        )
        return

    # Check QB connection
    statements = await svc.get_statements(clerk_user_id, ttl_minutes=15)
    if statements is None:
        await slack.send_reply(
            channel=channel,
            thread_ts=thread_ts,
            text="QuickBooks is not connected. Visit https://app.flowytics.com to connect.",
        )
        return

    financial_data = {
        "statements": [s.model_dump(mode="json") for s in statements],
        "current_cash": "0",
    }

    initial_state = {
        "user_id": clerk_user_id,
        "request_type": "slack",
        "request_params": {"question": text},
        "financial_data": financial_data,
        "cache_hit": True,
        "tool_results": {},
        "model_used": "",
        "llm_analysis": "",
        "llm_numbers": {},
        "discrepancies": [],
        "output": {},
    }

    result = await compiled_graph.ainvoke(initial_state)
    analysis = result["output"].get("analysis", "Sorry, I couldn't generate a response.")

    await slack.send_reply(channel=channel, thread_ts=thread_ts, text=analysis)


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """
    Handle Slack Events API callbacks (messages, app mentions).
    Responds immediately (200) and processes in background to avoid Slack timeout.
    """
    body = await request.body()

    # URL verification challenge (one-time setup)
    try:
        parsed = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if parsed.get("type") == "url_verification":
        return Response(content=parsed["challenge"], media_type="text/plain")

    # Verify Slack signature
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not _verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # Handle message events
    event = parsed.get("event", {})
    event_type = event.get("type", "")

    if event_type in ("message", "app_mention") and "bot_id" not in event:
        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")
        background_tasks.add_task(_handle_message, event, channel, thread_ts)

    return Response(status_code=200)
