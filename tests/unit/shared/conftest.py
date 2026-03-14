from __future__ import annotations

from unittest.mock import MagicMock


def _make_request(headers: dict, client_host: str = "10.0.0.1") -> MagicMock:
    """Minimal mock of a FastAPI Request."""
    req = MagicMock()
    req.headers = headers
    req.client = MagicMock()
    req.client.host = client_host
    return req
