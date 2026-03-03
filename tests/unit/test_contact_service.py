"""Unit tests for Phase 9 — ContactService."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from errors import AppError, ForbiddenError, ValidationError


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_service(captcha_ok=True, contact_sent=True, report_sent=True):
    from services.contact_service import ContactService

    contact_webhook = AsyncMock()
    report_webhook = AsyncMock()
    captcha = AsyncMock()

    captcha.verify = AsyncMock(return_value=captcha_ok)
    contact_webhook.send = AsyncMock(return_value=contact_sent)
    report_webhook.send = AsyncMock(return_value=report_sent)

    svc = ContactService(
        contact_webhook=contact_webhook,
        report_webhook=report_webhook,
        captcha=captcha,
    )
    return svc, contact_webhook, report_webhook, captcha


# ── Tests: send_contact_message ───────────────────────────────────────────────


class TestSendContactMessage:
    @pytest.mark.asyncio
    async def test_success_does_not_raise(self):
        svc, _, _, _ = make_service(captcha_ok=True, contact_sent=True)
        await svc.send_contact_message(
            email="user@example.com",
            message="Hello",
            captcha_token="valid-token",
        )

    @pytest.mark.asyncio
    async def test_captcha_failure_raises_forbidden(self):
        svc, _, _, _ = make_service(captcha_ok=False)

        with pytest.raises(ForbiddenError, match="Invalid captcha"):
            await svc.send_contact_message(
                email="user@example.com",
                message="Hello",
                captcha_token="bad-token",
            )

    @pytest.mark.asyncio
    async def test_webhook_failure_raises_app_error(self):
        svc, _, _, _ = make_service(captcha_ok=True, contact_sent=False)

        with pytest.raises(AppError, match="Error sending message"):
            await svc.send_contact_message(
                email="user@example.com",
                message="Hello",
                captcha_token="valid-token",
            )

    @pytest.mark.asyncio
    async def test_captcha_verified_before_webhook(self):
        """Captcha must be checked before the webhook is called."""
        svc, contact_webhook, _, captcha = make_service(captcha_ok=False)

        with pytest.raises(ForbiddenError):
            await svc.send_contact_message(
                email="user@example.com",
                message="Hello",
                captcha_token="bad-token",
            )

        contact_webhook.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_webhook_called_with_embed_payload(self):
        svc, contact_webhook, _, _ = make_service()
        await svc.send_contact_message(
            email="user@example.com",
            message="Test message",
            captcha_token="valid-token",
        )
        contact_webhook.send.assert_awaited_once()
        payload = contact_webhook.send.call_args[0][0]
        assert "embeds" in payload
        assert len(payload["embeds"]) == 1

    @pytest.mark.asyncio
    async def test_embed_contains_email_and_message(self):
        svc, contact_webhook, _, _ = make_service()
        await svc.send_contact_message(
            email="user@example.com",
            message="My message",
            captcha_token="valid-token",
        )
        embed = contact_webhook.send.call_args[0][0]["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Email" in field_names
        assert "Message" in field_names

    @pytest.mark.asyncio
    async def test_embed_title_is_new_contact_message(self):
        svc, contact_webhook, _, _ = make_service()
        await svc.send_contact_message(
            email="user@example.com",
            message="Hello",
            captcha_token="valid-token",
        )
        embed = contact_webhook.send.call_args[0][0]["embeds"][0]
        assert "Contact" in embed["title"]

    @pytest.mark.asyncio
    async def test_report_webhook_not_called_for_contact(self):
        svc, _, report_webhook, _ = make_service()
        await svc.send_contact_message(
            email="user@example.com",
            message="Hello",
            captcha_token="valid-token",
        )
        report_webhook.send.assert_not_awaited()


# ── Tests: send_report ────────────────────────────────────────────────────────


class TestSendReport:
    @pytest.mark.asyncio
    async def test_success_does_not_raise(self):
        svc, _, _, _ = make_service(captcha_ok=True, report_sent=True)
        await svc.send_report(
            short_code="abc123",
            reason="spam",
            ip_address="1.2.3.4",
            app_url="https://spoo.me/",
            captcha_token="valid-token",
            url_exists=True,
        )

    @pytest.mark.asyncio
    async def test_captcha_failure_raises_forbidden(self):
        svc, _, _, _ = make_service(captcha_ok=False)

        with pytest.raises(ForbiddenError, match="Invalid captcha"):
            await svc.send_report(
                short_code="abc123",
                reason="spam",
                ip_address="1.2.3.4",
                app_url="https://spoo.me/",
                captcha_token="bad-token",
                url_exists=True,
            )

    @pytest.mark.asyncio
    async def test_url_not_found_raises_validation_error(self):
        svc, _, _, _ = make_service(captcha_ok=True)

        with pytest.raises(ValidationError, match="Invalid short code"):
            await svc.send_report(
                short_code="ghost",
                reason="spam",
                ip_address="1.2.3.4",
                app_url="https://spoo.me/",
                captcha_token="valid-token",
                url_exists=False,
            )

    @pytest.mark.asyncio
    async def test_webhook_failure_raises_app_error(self):
        svc, _, _, _ = make_service(captcha_ok=True, report_sent=False)

        with pytest.raises(AppError, match="Error sending report"):
            await svc.send_report(
                short_code="abc123",
                reason="spam",
                ip_address="1.2.3.4",
                app_url="https://spoo.me/",
                captcha_token="valid-token",
                url_exists=True,
            )

    @pytest.mark.asyncio
    async def test_captcha_checked_before_existence(self):
        """Captcha must fail fast before the url_exists check matters."""
        svc, _, report_webhook, captcha = make_service(captcha_ok=False)

        with pytest.raises(ForbiddenError):
            await svc.send_report(
                short_code="abc123",
                reason="spam",
                ip_address="1.2.3.4",
                app_url="https://spoo.me/",
                captcha_token="bad-token",
                url_exists=True,
            )

        report_webhook.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_webhook_called_with_embed_payload(self):
        svc, _, report_webhook, _ = make_service()
        await svc.send_report(
            short_code="abc123",
            reason="phishing",
            ip_address="1.2.3.4",
            app_url="https://spoo.me/",
            captcha_token="valid-token",
            url_exists=True,
        )
        report_webhook.send.assert_awaited_once()
        payload = report_webhook.send.call_args[0][0]
        assert "embeds" in payload

    @pytest.mark.asyncio
    async def test_embed_contains_short_code_reason_ip(self):
        svc, _, report_webhook, _ = make_service()
        await svc.send_report(
            short_code="abc123",
            reason="phishing",
            ip_address="1.2.3.4",
            app_url="https://spoo.me/",
            captcha_token="valid-token",
            url_exists=True,
        )
        embed = report_webhook.send.call_args[0][0]["embeds"][0]
        field_names = [f["name"] for f in embed["fields"]]
        assert "Short Code" in field_names
        assert "Reason" in field_names
        assert "IP Address" in field_names

    @pytest.mark.asyncio
    async def test_embed_title_contains_short_code(self):
        svc, _, report_webhook, _ = make_service()
        await svc.send_report(
            short_code="abc123",
            reason="spam",
            ip_address="1.2.3.4",
            app_url="https://spoo.me/",
            captcha_token="valid-token",
            url_exists=True,
        )
        embed = report_webhook.send.call_args[0][0]["embeds"][0]
        assert "abc123" in embed["title"]

    @pytest.mark.asyncio
    async def test_embed_url_points_to_stats_page(self):
        svc, _, report_webhook, _ = make_service()
        await svc.send_report(
            short_code="abc123",
            reason="spam",
            ip_address="1.2.3.4",
            app_url="https://spoo.me/",
            captcha_token="valid-token",
            url_exists=True,
        )
        embed = report_webhook.send.call_args[0][0]["embeds"][0]
        assert embed["url"] == "https://spoo.me/stats/abc123"

    @pytest.mark.asyncio
    async def test_contact_webhook_not_called_for_report(self):
        svc, contact_webhook, _, _ = make_service()
        await svc.send_report(
            short_code="abc123",
            reason="spam",
            ip_address="1.2.3.4",
            app_url="https://spoo.me/",
            captcha_token="valid-token",
            url_exists=True,
        )
        contact_webhook.send.assert_not_awaited()
