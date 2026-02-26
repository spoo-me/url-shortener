"""
Random code and token generators — pure, side-effect-free functions.

All generators use cryptographically secure sources (``secrets`` module) or
the system PRNG where security is not required (alias generation).
"""

from __future__ import annotations

import random
import secrets
import string

from emojies import EMOJIES


def generate_short_code() -> str:
    """Generate a 6-character alphanumeric short code (legacy v1 schema)."""
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for _ in range(6))


def generate_short_code_v2(length: int = 7) -> str:
    """Generate an alphanumeric short code of configurable length (v2 schema).

    Args:
        length: Number of characters (default 7).

    Returns:
        Random alphanumeric string of the requested length.
    """
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for _ in range(length))


def generate_emoji_alias() -> str:
    """Generate a 3-emoji alias from the curated EMOJIES list."""
    return "".join(random.choice(EMOJIES) for _ in range(3))


def generate_otp_code(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP.

    Args:
        length: Number of digits (default 6).

    Returns:
        String of random decimal digits.
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe random token.

    Args:
        length: Number of random bytes before base64 encoding (default 32).
            The resulting string will be longer than *length* characters.

    Returns:
        URL-safe base64-encoded token string.
    """
    return secrets.token_urlsafe(length)
