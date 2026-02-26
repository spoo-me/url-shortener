"""
Bot detection utilities — framework-agnostic.

Combines two detection methods:
1. ``crawlerdetect`` library (signature-based)
2. BOT_USER_AGENTS regex patterns loaded lazily from ``bot_user_agents.txt``

The pattern file is loaded once via ``functools.lru_cache`` so there is no
import-time I/O (unlike the original ``utils/url_utils.py``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from crawlerdetect import CrawlerDetect

_crawler_detect = CrawlerDetect()


@lru_cache(maxsize=1)
def _load_bot_user_agents() -> list[str]:
    """Load and cache bot UA patterns from ``bot_user_agents.txt``.

    Returns an empty list if the file cannot be read so that callers
    degrade gracefully rather than raising at import time.
    """
    try:
        with open("bot_user_agents.txt", "r") as fh:
            return [line.strip() for line in fh if line.strip()]
    except OSError:
        return []


def is_bot_request(user_agent: str) -> bool:
    """Return True if *user_agent* looks like an automated crawler or bot.

    Checks both the ``CrawlerDetect`` library signature database and the
    local ``bot_user_agents.txt`` regex patterns.

    Args:
        user_agent: The ``User-Agent`` header value.

    Returns:
        ``True`` if a bot signature is detected.
    """
    if _crawler_detect.isCrawler(user_agent):
        return True
    bot_patterns = _load_bot_user_agents()
    return any(
        re.search(pattern, user_agent, re.IGNORECASE) for pattern in bot_patterns
    )


def get_bot_name(user_agent: str) -> Optional[str]:
    """Return the name/pattern of the detected bot, or ``None`` for humans.

    Tries ``CrawlerDetect.getMatches()`` first, then falls back to the
    first matching pattern from ``bot_user_agents.txt``.

    Args:
        user_agent: The ``User-Agent`` header value.

    Returns:
        A string identifying the bot, or ``None`` if no bot was detected.
    """
    if not is_bot_request(user_agent):
        return None

    # CrawlerDetect match (may return a list or string)
    if _crawler_detect.isCrawler(user_agent):
        matches = _crawler_detect.getMatches()
        if matches:
            return str(matches)

    # Fall back to first regex match
    bot_patterns = _load_bot_user_agents()
    for pattern in bot_patterns:
        if re.search(pattern, user_agent, re.IGNORECASE):
            return pattern

    return None
