"""
URL and input validators — framework-agnostic, pure functions.

All validators are stateless; any external data (e.g. blocked URL patterns)
must be passed in as arguments so the service/repository layer controls
caching and DB access.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
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
    return not re.search(r"[@.]{2}", password)


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
    return not (len(extracted_emojis) != len(alias) or len(emoji_list) > 15)


def validate_account_password(password: str) -> tuple[bool, list[str], int]:
    """Validate a user account password.

    Rules: ≥8 chars, ≤128 chars, uppercase, lowercase, digit, special char,
    no invalid characters.

    Returns:
        (is_valid, missing_requirements, strength_score)
    """
    if not password:
        return False, ["Password is required"], 0

    missing: list[str] = []
    strength_score = 0

    if len(password) < 8:
        missing.append("At least 8 characters")
    else:
        strength_score += 20

    if len(password) > 128:
        missing.append("Maximum 128 characters")
    else:
        strength_score += 10

    if not re.search(r"[A-Z]", password):
        missing.append("At least one uppercase letter")
    else:
        strength_score += 15

    if not re.search(r"[a-z]", password):
        missing.append("At least one lowercase letter")
    else:
        strength_score += 15

    if not re.search(r"[0-9]", password):
        missing.append("At least one number")
    else:
        strength_score += 15

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
        missing.append("At least one special character")
    else:
        strength_score += 15

    if not re.match(
        r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`\s]+$', password
    ):
        missing.append("Contains invalid characters")
    else:
        strength_score += 10

    if len(password) >= 12:
        strength_score += 5
    if len(password) >= 16:
        strength_score += 5

    if re.search(r"(.)\1{2,}", password):
        strength_score -= 10

    if re.search(
        r"(012|123|234|345|456|567|678|789|890|abc|bcd|cde|def)", password.lower()
    ):
        strength_score -= 15

    for pattern in [r"password", r"123456", r"qwerty", r"admin", r"login", r"welcome"]:
        if re.search(pattern, password.lower()):
            strength_score -= 20
            break

    return len(missing) == 0, missing, strength_score


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
