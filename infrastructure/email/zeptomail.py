"""ZeptoMail implementation of EmailProvider.

Ported from utils/email_service.py:
- sync requests → async httpx via HttpClient
- module-level os.getenv → injected EmailSettings + app_url
- Jinja2 template rendering is unchanged
"""

import os
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import EmailSettings
from infrastructure.http_client import HttpClient
from shared.logging import get_logger

log = get_logger(__name__)

_ZEPTO_API_URL = "https://api.zeptomail.in/v1.1/email"
_DEFAULT_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "templates",
    "emails",
)


class ZeptoMailProvider:
    def __init__(
        self,
        settings: EmailSettings,
        http_client: HttpClient,
        app_url: str = "https://spoo.me",
        template_dir: str = _DEFAULT_TEMPLATE_DIR,
    ) -> None:
        self._settings = settings
        self._http = http_client
        self._app_url = app_url
        self._jinja = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def _send(
        self,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        if not self._settings.zepto_api_token:
            log.error("zepto_mail_send_failed", reason="token_not_configured")
            return False

        payload: dict = {
            "from": {
                "address": self._settings.zepto_from_email,
                "name": self._settings.zepto_from_name,
            },
            "to": [
                {
                    "email_address": {
                        "address": to_email,
                        "name": to_name or to_email,
                    }
                }
            ],
            "subject": subject,
            "htmlbody": html_body,
        }
        if text_body:
            payload["textbody"] = text_body

        token = self._settings.zepto_api_token
        if not token.startswith("Zoho-enczapikey "):
            token = f"Zoho-enczapikey {token}"

        headers = {"Authorization": token, "Content-Type": "application/json"}

        try:
            response = await self._http.post(
                _ZEPTO_API_URL, json=payload, headers=headers
            )
            if response.status_code in (200, 201, 202):
                log.info("email_sent_success", to_email=to_email, subject=subject)
                return True
            log.error(
                "email_sent_failed",
                to_email=to_email,
                subject=subject,
                status_code=response.status_code,
                response=response.text[:200],
            )
            return False
        except Exception as e:
            log.error(
                "email_send_error",
                to_email=to_email,
                subject=subject,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def send_verification_email(
        self, email: str, user_name: Optional[str], otp_code: str
    ) -> bool:
        subject = "Verify your email - spoo.me"
        template = self._jinja.get_template("verification.html")
        html_body = template.render(
            otp_code=otp_code, user_name=user_name, app_url=self._app_url
        )
        text_body = (
            f"Verify Your Email - spoo.me\n\n"
            f"Hello{f' {user_name}' if user_name else ''},\n\n"
            f"Your verification code is: {otp_code}\n\n"
            f"This code expires in 10 minutes.\n\n"
            f"© 2025 spoo.me. All rights reserved."
        )
        return await self._send(email, user_name, subject, html_body, text_body)

    async def send_welcome_email(self, email: str, user_name: Optional[str]) -> bool:
        subject = "Welcome to spoo.me! 🎉"
        template = self._jinja.get_template("welcome.html")
        html_body = template.render(user_name=user_name, app_url=self._app_url)
        text_body = (
            f"Welcome to spoo.me{f', {user_name}' if user_name else ''}!\n\n"
            f"Get started: {self._app_url}/dashboard\n\n"
            f"© 2025 spoo.me. All rights reserved."
        )
        return await self._send(email, user_name, subject, html_body, text_body)

    async def send_password_reset_email(
        self, email: str, user_name: Optional[str], otp_code: str
    ) -> bool:
        subject = "Reset your password - spoo.me"
        template = self._jinja.get_template("password_reset.html")
        html_body = template.render(
            otp_code=otp_code, user_name=user_name, app_url=self._app_url
        )
        text_body = (
            f"Reset Your Password - spoo.me\n\n"
            f"Hello{f' {user_name}' if user_name else ''},\n\n"
            f"Your password reset code is: {otp_code}\n\n"
            f"This code expires in 10 minutes.\n\n"
            f"© 2025 spoo.me. All rights reserved."
        )
        return await self._send(email, user_name, subject, html_body, text_body)
