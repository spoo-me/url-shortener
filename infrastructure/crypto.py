"""
Cryptographic helpers — password hashing and token hashing.

Uses argon2 for passwords (via argon2-cffi) and SHA-256 for token hashing.
"""

from __future__ import annotations

import hashlib

from argon2 import PasswordHasher

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash *plain_password* with argon2id.

    Returns:
        Argon2 hash string (includes algorithm parameters and salt).
    """
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify *plain_password* against an argon2 *password_hash*.

    Returns:
        ``True`` if the password matches, ``False`` for any failure
        (wrong password, invalid hash, etc.).
    """
    try:
        _password_hasher.verify(password_hash, plain_password)
        return True
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Return the hex-encoded SHA-256 digest of *token*.

    Used to hash OTP codes and secure tokens before storing them in the
    database so the plaintext is never persisted.

    Args:
        token: The plaintext token string to hash.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
