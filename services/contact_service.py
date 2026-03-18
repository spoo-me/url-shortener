"""
ContactService — contact form and URL report handling.

Validates captcha via CaptchaProvider, then dispatches to the appropriate
Discord webhook via WebhookProvider.  Framework-agnostic: no FastAPI imports.

The route layer is responsible for:
    - Parsing form data (email, message, short_code, reason, captcha token)
    - Checking that the reported short_code exists (via UrlService)
    - HTTP response construction (redirect or render template)

Discord embed payloads are built here to keep webhook formatting logic in
one place.  The WebhookProvider only handles the actual HTTP transport.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from errors import AppError, ForbiddenError, ValidationError
from infrastructure.captcha.protocol import CaptchaProvider
from infrastructure.webhook.protocol import WebhookProvider
from shared.logging import get_logger

log = get_logger(__name__)


class ContactService:
    """Contact and report form service.

    Args:
        contact_webhook: WebhookProvider wired to the contact Discord webhook URL.
        report_webhook:  WebhookProvider wired to the URL-report Discord webhook URL.
        captcha:         CaptchaProvider used to verify hCaptcha tokens.
    """

    def __init__(
        self,
        contact_webhook: WebhookProvider,
        report_webhook: WebhookProvider,
        captcha: CaptchaProvider,
    ) -> None:
        self._contact_webhook = contact_webhook
        self._report_webhook = report_webhook
        self._captcha = captcha

    # ── Private: embed builders ───────────────────────────────────────────────

    @staticmethod
    def _contact_embed(email: str, message: str) -> dict[str, Any]:
        """Build the Discord embed payload for a contact message.

        Preserves the exact embed structure from utils/contact_utils.send_contact_message().
        """
        return {
            "embeds": [
                {
                    "title": "New Contact Message ✉️",
                    "color": 9103397,
                    "fields": [
                        {"name": "Email", "value": f"```{email}```"},
                        {"name": "Message", "value": f"```{message}```"},
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {
                        "text": "spoo-me",
                        "icon_url": "https://spoo.me/static/images/favicon.png",
                    },
                }
            ]
        }

    @staticmethod
    def _report_embed(
        short_code: str,
        reason: str,
        ip_address: str,
        app_url: str,
    ) -> dict[str, Any]:
        """Build the Discord embed payload for a URL report.

        Preserves the exact embed structure from utils/contact_utils.send_report().
        """
        return {
            "embeds": [
                {
                    "title": f"URL Report for `{short_code}`",
                    "color": 14177041,
                    "url": f"{app_url}stats/{short_code}",
                    "fields": [
                        {"name": "Short Code", "value": f"```{short_code}```"},
                        {"name": "Reason", "value": f"```{reason}```"},
                        {"name": "IP Address", "value": f"```{ip_address}```"},
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {
                        "text": "spoo-me",
                        "icon_url": "https://spoo.me/static/images/favicon.png",
                    },
                }
            ]
        }

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_contact_message(
        self,
        email: str,
        message: str,
        captcha_token: str,
    ) -> None:
        """Send a contact form message to the Discord contact webhook.

        Args:
            email:         Sender's email address.
            message:       Message body.
            captcha_token: hCaptcha response token from the form.

        Raises:
            ForbiddenError: Captcha verification failed.
            AppError:       Webhook send failed.
        """
        if not await self._captcha.verify(captcha_token):
            log.warning("contact_captcha_failed")
            raise ForbiddenError("Invalid captcha, please try again")

        payload = self._contact_embed(email, message)
        sent = await self._contact_webhook.send(payload)
        if not sent:
            log.error(
                "contact_webhook_send_failed",
                email_domain=email.split("@")[1] if "@" in email else "unknown",
            )
            raise AppError("Error sending message, please try again later")

        log.info(
            "contact_message_sent",
            email_domain=email.split("@")[1] if "@" in email else "unknown",
            message_length=len(message),
        )

    async def send_report(
        self,
        short_code: str,
        reason: str,
        ip_address: str,
        app_url: str,
        captcha_token: str,
        url_exists: bool,
    ) -> None:
        """Send a URL report to the Discord report webhook.

        Args:
            short_code:    The reported short code (already stripped to base code).
            reason:        Reporter's reason.
            ip_address:    Reporter's client IP.
            app_url:       Base URL of the application (e.g. ``"https://spoo.me/"``).
            captcha_token: hCaptcha response token.
            url_exists:    Whether the short_code was found in any URL collection.
                           The route layer performs the existence check.

        Raises:
            ForbiddenError:  Captcha verification failed.
            ValidationError: short_code does not exist.
            AppError:        Webhook send failed.
        """
        if not await self._captcha.verify(captcha_token):
            log.warning("report_captcha_failed", short_code=short_code)
            raise ForbiddenError("Invalid captcha, please try again")

        if not url_exists:
            raise ValidationError("Invalid short code, short code does not exist")

        payload = self._report_embed(short_code, reason, ip_address, app_url)
        sent = await self._report_webhook.send(payload)
        if not sent:
            log.error(
                "report_webhook_send_failed",
                short_code=short_code,
            )
            raise AppError("Error sending report, please try again later")

        log.info("url_report_sent", short_code=short_code, reason=reason[:50])
