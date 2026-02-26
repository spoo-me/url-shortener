"""
URL and input validators — framework-agnostic, pure functions.

All validators are stateless; any external data (e.g. blocked URL patterns)
must be passed in as arguments so the service/repository layer controls
caching and DB access.
"""

from __future__ import annotations

import re
from typing import Sequence
from urllib.parse import unquote

import emoji
import regex
import validators as _validators


def validate_url(
    url: str,
    blocked_self_domains: Sequence[str] = ("spoo.me",),
) -> bool:
    """Return True if *url* is a valid, non-self-referential HTTP/S URL.

    Args:
        url: The URL string to validate.
        blocked_self_domains: Domain strings that must not appear in the URL.
            Defaults to ``("spoo.me",)`` to prevent redirect loops.

    Returns:
        True when the URL passes format validation AND none of the blocked
        domains appear in it.
    """
    if not _validators.url(url, skip_ipv4_addr=True, skip_ipv6_addr=True):
        return False
    url_lower = url.lower()
    return not any(domain in url_lower for domain in blocked_self_domains)


def validate_url_password(password: str) -> bool:
    """Validate a URL password.

    Rules:
    - At least 8 characters
    - Contains at least one letter
    - Contains at least one digit
    - Contains at least one of ``@`` or ``.``
    - No two consecutive special characters (``@@``, ``..``, ``@.``, ``.@``)

    Returns:
        True if the password meets all requirements.
    """
    if len(password) < 8:
        return False
    if not re.search(r"[a-zA-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[@.]", password):
        return False
    if re.search(r"[@.]{2}", password):
        return False
    return True


def validate_alias(alias: str) -> bool:
    """Return True if *alias* contains only alphanumeric characters, ``-``, or ``_``."""
    return bool(re.search(r"^[a-zA-Z0-9_-]*$", alias))


def validate_emoji_alias(alias: str) -> bool:
    """Return True if *alias* is a valid emoji-only alias (max 15 emojis).

    The alias is URL-decoded before validation so percent-encoded emojis are
    handled correctly.
    """
    alias = unquote(alias)
    emoji_list = emoji.emoji_list(alias)
    extracted_emojis = "".join([data["emoji"] for data in emoji_list])
    if len(extracted_emojis) != len(alias) or len(emoji_list) > 15:
        return False
    return True


def validate_blocked_url(url: str, patterns: Sequence[str]) -> bool:
    """Return True if *url* does NOT match any blocked pattern.

    This is a pure function — the caller is responsible for providing the
    list of blocked URL regex patterns (typically loaded from the database
    and cached by the repository layer).

    Uses the ``regex`` library with a per-pattern timeout of 200 ms to
    prevent ReDoS attacks on user-supplied patterns.

    Args:
        url: The URL to check.
        patterns: Iterable of regex pattern strings to match against.

    Returns:
        True if the URL is allowed (no pattern matched), False if blocked.
    """
    for pattern in patterns:
        try:
            if regex.search(pattern, url, timeout=0.2):
                return False
        except TimeoutError:
            pass  # Treat timed-out patterns as non-matching (fail open)
    return True
