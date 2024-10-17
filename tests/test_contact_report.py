import pytest
import requests
import requests_mock
from utils import send_report, send_contact_message
from datetime import datetime, timezone


def test_send_report_success(mocker):
    webhook_uri = "https://discord.com/api/webhooks/test_webhook"
    short_code = "abc123"
    reason = "Test Reason"
    ip_address = "192.168.1.1"
    host_uri = "https://example.com/"

    with requests_mock.Mocker() as m:
        m.post(webhook_uri, status_code=200)
        send_report(webhook_uri, short_code, reason, ip_address, host_uri)
        assert m.called
        assert m.call_count == 1
        request = m.request_history[0]
        expected_data = {
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
                    "footer": {
                        "text": "spoo-me",
                        "icon_url": "https://spoo.me/static/images/favicon.png",
                    },
                }
            ]
        }
        actual_data = request.json()
        actual_data["embeds"][0].pop("timestamp")

        # Check if the request JSON matches the expected data
        assert actual_data == expected_data


def test_send_report_failure(mocker):
    webhook_uri = "https://discord.com/api/webhooks/test_webhook"
    short_code = "abc123"
    reason = "Test Reason"
    ip_address = "192.168.1.1"
    host_uri = "https://example.com/"

    with requests_mock.Mocker() as m:
        m.post(webhook_uri, status_code=500)
        send_report(webhook_uri, short_code, reason, ip_address, host_uri)
        assert m.called
        assert m.call_count == 1


def test_send_contact_message_success(mocker):
    webhook_uri = "https://discord.com/api/webhooks/test_webhook"
    email = "test@example.com"
    message = "This is a test message."

    with requests_mock.Mocker() as m:
        m.post(webhook_uri, status_code=200)
        send_contact_message(webhook_uri, email, message)
        assert m.called
        assert m.call_count == 1
        request = m.request_history[0]
        expected_data = {
            "embeds": [
                {
                    "title": "New Contact Message ✉️",
                    "color": 9103397,
                    "fields": [
                        {"name": "Email", "value": f"```{email}```"},
                        {"name": "Message", "value": f"```{message}```"},
                    ],
                    "footer": {
                        "text": "spoo-me",
                        "icon_url": "https://spoo.me/static/images/favicon.png",
                    },
                }
            ]
        }
        actual_data = request.json()
        del actual_data["embeds"][0]["timestamp"]

        # Check if the request JSON matches the expected data
        assert actual_data == expected_data


def test_send_contact_message_failure(mocker):
    webhook_uri = "https://discord.com/api/webhooks/test_webhook"
    email = "test@example.com"
    message = "This is a test message."

    with requests_mock.Mocker() as m:
        m.post(webhook_uri, status_code=500)
        send_contact_message(webhook_uri, email, message)
        assert m.called
        assert m.call_count == 1
