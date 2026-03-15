"""
Shared fixtures for all integration tests.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from middleware.rate_limiter import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the in-memory rate limiter before and after every integration test.

    The slowapi limiter is a module-level singleton with in-memory storage
    during tests. Without this reset, rate limit counters leak across test
    files and cause spurious 429 failures.
    """
    limiter.reset()
    yield
    limiter.reset()
