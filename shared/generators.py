"""
Random code and token generators — pure, side-effect-free functions.

All generators use cryptographically secure sources (``secrets`` module) or
the system PRNG where security is not required (alias generation).
"""

from __future__ import annotations

import json
import random
import secrets
import string
from functools import lru_cache
from pathlib import Path

_EMOJIS_PATH = Path(__file__).resolve().parent.parent / "data" / "emojis.json"


@lru_cache(maxsize=1)
def _load_emojis() -> list[str]:
    with open(_EMOJIS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not data:
        raise ValueError(
            f"emojis.json must be a non-empty list, got {type(data).__name__}"
        )
    return data


def generate_short_code() -> str:
    """Generate a 6-character alphanumeric short code (legacy v1 schema)."""
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for _ in range(6))


def generate_short_code_v2(length: int = 7) -> str:
    """Generate an alphanumeric short code of configurable length (v2 schema).

    Args:
        length: Number of characters (default 7, must be 1-255).

    Returns:
        Random alphanumeric string of the requested length.
    """
    if length < 1 or length > 255:
        raise ValueError("length must be between 1 and 255")
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for _ in range(length))


def generate_emoji_alias() -> str:
    """Generate a 3-emoji alias from the curated emoji list."""
    return "".join(random.choice(_load_emojis()) for _ in range(3))


def generate_otp_code(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP.

    Args:
        length: Number of digits (default 6, must be 1-128).

    Returns:
        String of random decimal digits.
    """
    if length < 1 or length > 128:
        raise ValueError("length must be between 1 and 128")
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
