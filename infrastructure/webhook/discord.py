"""Discord webhook implementation of WebhookProvider.

Ported from utils/contact_utils.py (send_report / send_contact_message):
- sync requests → async httpx via HttpClient
- module-level os.getenv → injected webhook URL
- accepts a generic payload dict; callers build the Discord embed structure
"""

from typing import Any

from infrastructure.http_client import HttpClient
from shared.logging import get_logger

log = get_logger(__name__)


class DiscordWebhookProvider:
    def __init__(self, webhook_url: str, http_client: HttpClient) -> None:
        self._webhook_url = webhook_url
        self._http = http_client

    async def send(self, payload: dict[str, Any]) -> bool:
        if not self._webhook_url:
            log.warning("discord_webhook_not_configured")
            return False
        try:
            response = await self._http.post(self._webhook_url, json=payload)
            if response.status_code in (200, 204):
                return True
            log.warning(
                "discord_webhook_failed",
                status_code=response.status_code,
                response_text=response.text[:200],
            )
            return False
        except Exception as e:
            log.error(
                "discord_webhook_request_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
