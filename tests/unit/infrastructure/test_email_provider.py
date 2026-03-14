"""Unit tests for ZeptoMailProvider."""

from unittest.mock import AsyncMock, MagicMock

from config import EmailSettings
from infrastructure.email.zeptomail import ZeptoMailProvider


class TestZeptoMailProvider:
    def _make(self, token="test-token"):
        settings = EmailSettings(
            zepto_api_token=token,
            zepto_from_email="noreply@spoo.me",
            zepto_from_name="spoo.me",
        )
        http = MagicMock()
        # Patch template rendering so tests don't need real template files
        jinja = MagicMock()
        jinja.get_template.return_value.render.return_value = "<html>test</html>"
        provider = ZeptoMailProvider(
            settings=settings, http_client=http, app_url="https://spoo.me"
        )
        provider._jinja = jinja
        return provider, http

    async def test_send_verification_makes_post(self):
        provider, http = self._make()
        resp = MagicMock(status_code=200)
        http.post = AsyncMock(return_value=resp)
        result = await provider.send_verification_email(
            "user@example.com", "Alice", "123456"
        )
        assert result is True
        http.post.assert_awaited_once()

    async def test_returns_false_when_token_empty(self):
        provider, _ = self._make(token="")
        assert (
            await provider.send_verification_email("u@e.com", None, "000000") is False
        )

    async def test_returns_false_on_non_2xx(self):
        provider, http = self._make()
        resp = MagicMock(status_code=422, text="Unprocessable")
        http.post = AsyncMock(return_value=resp)
        assert (
            await provider.send_verification_email("u@e.com", None, "000000") is False
        )

    async def test_returns_false_on_exception(self):
        provider, http = self._make()
        http.post = AsyncMock(side_effect=Exception("timeout"))
        assert (
            await provider.send_verification_email("u@e.com", None, "000000") is False
        )

    async def test_auth_header_prepends_prefix(self):
        provider, http = self._make(token="rawtoken")
        resp = MagicMock(status_code=200)
        http.post = AsyncMock(return_value=resp)
        await provider.send_welcome_email("u@e.com", "Alice")
        _, kwargs = http.post.call_args
        auth = kwargs["headers"]["Authorization"]
        assert auth == "Zoho-enczapikey rawtoken"

    async def test_auth_header_not_double_prefixed(self):
        provider, http = self._make(token="Zoho-enczapikey alreadyprefixed")
        resp = MagicMock(status_code=201)
        http.post = AsyncMock(return_value=resp)
        await provider.send_password_reset_email("u@e.com", None, "654321")
        _, kwargs = http.post.call_args
        auth = kwargs["headers"]["Authorization"]
        assert auth.count("Zoho-enczapikey") == 1
