"""Shared async HTTP client with configurable timeout."""

from typing import Any

import httpx


class HttpClient:
    """Thin async wrapper around httpx.AsyncClient with a configurable timeout.

    One instance per external service keeps timeouts independently configurable.
    """

    def __init__(self, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(url, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
