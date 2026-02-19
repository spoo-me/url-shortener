import requests
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()

log = get_logger(__name__)

CONTACT_WEBHOOK = os.environ.get("CONTACT_WEBHOOK")
URL_REPORT_WEBHOOK = os.environ.get("URL_REPORT_WEBHOOK")
hcaptcha_secret = os.environ.get("HCAPTCHA_SECRET")


def verify_hcaptcha(token):
    hcaptcha_verify_url = "https://hcaptcha.com/siteverify"

    try:
        response = requests.post(
            hcaptcha_verify_url,
            data={
                "response": token,
                "secret": hcaptcha_secret,
            },
            timeout=5,
        )

        if response.status_code == 200:
            data = response.json()
            success = data.get("success", False)
            if not success:
                log.warning(
                    "hcaptcha_verification_failed",
                    error_codes=data.get("error-codes", []),
                )
            return success
        else:
            log.error(
                "hcaptcha_api_error",
                status_code=response.status_code,
                response_text=response.text[:200],
            )
            return False
    except requests.exceptions.RequestException as e:
        log.error("hcaptcha_request_failed", error=str(e), error_type=type(e).__name__)
        return False


def send_report(webhook_uri, short_code, reason, ip_address, host_uri):
    data = {
        "embeds": [
            {
                "title": f"URL Report for `{short_code}`",
                "color": 14177041,
                "url": f"{host_uri}stats/{short_code}",
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

    try:
        response = requests.post(webhook_uri, json=data, timeout=5)
        if response.status_code not in (200, 204):
            log.warning(
                "report_webhook_failed",
                short_code=short_code,
                status_code=response.status_code,
                response_text=response.text[:200],
            )
    except requests.exceptions.RequestException as e:
        log.error(
            "report_webhook_request_failed",
            short_code=short_code,
            error=str(e),
            error_type=type(e).__name__,
        )


def send_contact_message(webhook_uri, email, message):
    data = {
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

    try:
        response = requests.post(webhook_uri, json=data, timeout=5)
        if response.status_code not in (200, 204):
            log.warning(
                "contact_webhook_failed",
                email=email,
                status_code=response.status_code,
                response_text=response.text[:200],
            )
    except requests.exceptions.RequestException as e:
        log.error(
            "contact_webhook_request_failed",
            email=email,
            error=str(e),
            error_type=type(e).__name__,
        )
