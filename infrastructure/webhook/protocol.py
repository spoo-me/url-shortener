"""WebhookProvider protocol — services depend on this, not the concrete implementation."""

from typing import Any, Protocol


class WebhookProvider(Protocol):
    async def send(self, payload: dict[str, Any]) -> bool: ...
