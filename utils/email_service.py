"""
Email service using ZeptoMail for transactional emails
"""

import os
import requests
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils.logger import get_logger

log = get_logger(__name__)

# Initialize Jinja2 environment for email templates
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "emails")
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)

# ZeptoMail Configuration
ZEPTO_API_URL = "https://api.zeptomail.in/v1.1/email"
ZEPTO_API_TOKEN = os.getenv("ZEPTO_API_TOKEN", "")
ZEPTO_FROM_EMAIL = os.getenv("ZEPTO_FROM_EMAIL", "noreply@spoo.me")
ZEPTO_FROM_NAME = os.getenv("ZEPTO_FROM_NAME", "spoo.me")
APP_NAME = "spoo.me"
APP_URL = os.getenv("APP_URL", "https://spoo.me")


class ZeptoMailService:
    """Service for sending transactional emails via ZeptoMail API"""

    def __init__(self):
        self.api_url = ZEPTO_API_URL
        self.api_token = ZEPTO_API_TOKEN
        self.from_email = ZEPTO_FROM_EMAIL
        self.from_name = ZEPTO_FROM_NAME

        if not self.api_token:
            log.error(
                "zepto_mail_token_missing", message="ZEPTO_API_TOKEN not configured"
            )

    def _send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email via ZeptoMail API

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.api_token:
            log.error("zepto_mail_send_failed", reason="token_not_configured")
            return False

        try:
            # Prepare request payload
            payload = {
                "from": {
                    "address": self.from_email,
                    "name": self.from_name,
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

            # Prepare headers
            # Check if token already has the prefix
            auth_token = self.api_token
            if not auth_token.startswith("Zoho-enczapikey "):
                auth_token = f"Zoho-enczapikey {auth_token}"

            headers = {
                "Authorization": auth_token,
                "Content-Type": "application/json",
            }

            # Send request
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=10,
            )

            if response.status_code in [200, 201, 202]:
                log.info(
                    "email_sent_success",
                    to_email=to_email,
                    subject=subject,
                    status_code=response.status_code,
                )
                return True
            else:
                log.error(
                    "email_sent_failed",
                    to_email=to_email,
                    subject=subject,
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

        except requests.exceptions.Timeout:
            log.error("email_send_timeout", to_email=to_email, subject=subject)
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

    def send_verification_email(
        self, email: str, user_name: Optional[str], otp_code: str
    ) -> bool:
        """
        Send email verification OTP

        Args:
            email: Recipient email
            user_name: User's name
            otp_code: 6-digit OTP code

        Returns:
            True if sent successfully
        """
        subject = f"Verify your email - {APP_NAME}"

        # Render template
        template = jinja_env.get_template('verification.html')
        html_body = template.render(
            otp_code=otp_code,
            user_name=user_name,
            app_url=APP_URL
        )

        text_body = f"""
Verify Your Email - spoo.me

Hello{f" {user_name}" if user_name else ""},

We received a request to verify your email address for your spoo.me account. Please use the verification code below to complete the process:

{otp_code}

Enter this code in the verification field to complete your account setup. This code will expire in 10 minutes for security purposes.

If you didn't request this verification, please ignore this email or contact our support team if you have concerns.

Need help? Contact us at support@spoo.me

© 2025 spoo.me. All rights reserved.
        """

        return self._send_email(email, user_name, subject, html_body, text_body)

    def send_password_reset_email(
        self, email: str, user_name: Optional[str], otp_code: str
    ) -> bool:
        """
        Send password reset OTP

        Args:
            email: Recipient email
            user_name: User's name
            otp_code: 6-digit OTP code

        Returns:
            True if sent successfully
        """
        subject = "Reset your password - spoo.me"

        # Render template
        template = jinja_env.get_template('password_reset.html')
        html_body = template.render(
            otp_code=otp_code,
            user_name=user_name,
            app_url=APP_URL
        )

        text_body = f"""
Reset Your Password - spoo.me

Hello{f" {user_name}" if user_name else ""},

We received a request to reset your password for your spoo.me account. Please use the verification code below to proceed:

{otp_code}

Enter this code to reset your password. This code will expire in 10 minutes for security purposes.

⚠️ SECURITY NOTICE: If you didn't request a password reset, please ignore this email and consider changing your password immediately.

Need help? Contact us at support@spoo.me

© 2025 spoo.me. All rights reserved.
        """

        return self._send_email(email, user_name, subject, html_body, text_body)

    def send_welcome_email(self, email: str, user_name: Optional[str]) -> bool:
        """
        Send welcome email after successful verification

        Args:
            email: Recipient email
            user_name: User's name

        Returns:
            True if sent successfully
        """
        subject = "Welcome to spoo.me! 🎉"

        # Render template
        template = jinja_env.get_template('welcome.html')
        html_body = template.render(
            user_name=user_name,
            app_url=APP_URL
        )

        text_body = f"""
Welcome to spoo.me{f", {user_name}" if user_name else ""}! 🎉

Thank you for joining the modern URL shortener built for developers, marketers, and businesses who demand more from their links.

What makes spoo.me different?

🚀 Powerful Analytics
Track clicks, locations, devices, and referrers with detailed insights that help you understand your audience better.

⚡ Developer-Friendly API
Integrate seamlessly with our RESTful API and comprehensive documentation designed for modern development workflows.

🔒 Enterprise Security
Password protection, and expiration dates give you complete control over your links.

🔄 Link Management
Edit, pause, or delete links anytime with full control over your URLs.

Ready to get started?
1. Visit your dashboard to create your first short link
2. Explore our analytics to understand your audience
3. Check out our API documentation for advanced integrations

Get started: {APP_URL}/dashboard

Need help getting started? We're here to support you every step of the way.
Contact us at support@spoo.me

© 2025 spoo.me. All rights reserved.
        """

        return self._send_email(email, user_name, subject, html_body, text_body)


# Global instance
email_service = ZeptoMailService()
