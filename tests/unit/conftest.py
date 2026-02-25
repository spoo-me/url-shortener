"""
Unit test configuration.

Patches dotenv so pydantic-settings never reads the project's real .env file
during unit tests. Tests control config exclusively through monkeypatch.setenv().
"""

import pytest


@pytest.fixture(autouse=True)
def disable_dotenv_loading(monkeypatch):
    """Prevent pydantic-settings from loading .env files in all unit tests."""
    import pydantic_settings.sources.providers.dotenv as ps_dotenv

    monkeypatch.setattr(ps_dotenv, "dotenv_values", lambda *a, **kw: {})
