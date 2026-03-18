"""ClickHandler protocol and ClickContext dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from typing_extensions import Protocol

from infrastructure.cache.url_cache import UrlCacheData


@dataclass
class ClickContext:
    """All metadata available at click time, passed to the active handler."""

    url_data: UrlCacheData
    short_code: str
    client_ip: str
    start_time: float
    user_agent: str
    referrer: Optional[str]
    is_emoji: bool = False
    cf_city: Optional[str] = None


class ClickHandler(Protocol):
    """Minimal protocol every click handler must satisfy."""

    async def handle(self, context: ClickContext) -> None: ...
