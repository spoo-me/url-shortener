import requests
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

CONTACT_WEBHOOK = os.environ["CONTACT_WEBHOOK"]
URL_REPORT_WEBHOOK = os.environ["URL_REPORT_WEBHOOK"]
hcaptcha_secret = os.environ.get("HCAPTCHA_SECRET")


def verify_hcaptcha(token):
    hcaptcha_verify_url = "https://hcaptcha.com/siteverify"

    response = requests.post(
        hcaptcha_verify_url,
        data={
            "response": token,
            "secret": hcaptcha_secret,
        },
    )

    if response.status_code == 200:
        data = response.json()
        return data["success"]
    else:
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

    requests.post(webhook_uri, json=data)


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

    requests.post(webhook_uri, json=data)
