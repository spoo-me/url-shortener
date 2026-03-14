"""Unit tests for DiscordWebhookProvider."""

from unittest.mock import AsyncMock, MagicMock

from infrastructure.webhook.discord import DiscordWebhookProvider


class TestDiscordWebhookProvider:
    def _make(self, url="https://discord.com/api/webhooks/123/abc"):
        http = MagicMock()
        return DiscordWebhookProvider(webhook_url=url, http_client=http), http

    async def test_sends_payload_returns_true_on_204(self):
        provider, http = self._make()
        resp = MagicMock(status_code=204)
        http.post = AsyncMock(return_value=resp)
        assert await provider.send({"embeds": []}) is True

    async def test_sends_payload_returns_true_on_200(self):
        provider, http = self._make()
        resp = MagicMock(status_code=200)
        http.post = AsyncMock(return_value=resp)
        assert await provider.send({"embeds": []}) is True

    async def test_returns_false_on_error_status(self):
        provider, http = self._make()
        resp = MagicMock(status_code=400, text="Bad Request")
        http.post = AsyncMock(return_value=resp)
        assert await provider.send({}) is False

    async def test_returns_false_when_url_empty(self):
        provider, _ = self._make(url="")
        assert await provider.send({}) is False

    async def test_returns_false_on_exception(self):
        provider, http = self._make()
        http.post = AsyncMock(side_effect=Exception("network error"))
        assert await provider.send({}) is False
