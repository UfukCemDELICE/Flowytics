from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from backend.app.config import get_settings


class SlackClient:
    """Slack Bot API client for sending messages and handling conversations."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)

    async def send_message(self, channel: str, text: str) -> bool:
        """Send a message to a Slack channel or DM."""
        try:
            self.client.chat_postMessage(channel=channel, text=text)
            return True
        except SlackApiError:
            return False

    async def send_reply(self, channel: str, thread_ts: str, text: str) -> bool:
        """Reply in a Slack thread."""
        try:
            self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text,
            )
            return True
        except SlackApiError:
            return False
