"""The limiter must keep limiting, fast, when its Redis is down or wedged.

The limiter reads REDIS_URI at import, so each case imports it in a fresh
interpreter pointed at a broken Redis.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import textwrap

import pytest

_SCRIPT = textwrap.dedent(
    """
    import json, time
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from app.middleware.rate_limiter import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/x")
    @limiter.limit("2 per minute")
    async def x(request: Request):
        return {}

    with TestClient(app, raise_server_exceptions=False) as c:
        start = time.monotonic()
        codes = [c.get("/x").status_code for _ in range(3)]
        print(json.dumps({"codes": codes, "elapsed": time.monotonic() - start}))
    """
)


def _run(redis_uri: str) -> dict:
    env = {**os.environ, "REDIS_URI": redis_uri, "MONGODB_URI": "mongodb://x/"}
    out = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.fixture
def black_hole():
    """A port that completes the TCP handshake and never answers."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(64)
    yield f"redis://127.0.0.1:{sock.getsockname()[1]}/0"
    sock.close()


@pytest.fixture
def refused():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"redis://127.0.0.1:{port}/0"


@pytest.mark.parametrize("uri_fixture", ["refused", "black_hole"])
def test_limiter_falls_back_to_memory_when_redis_is_unusable(uri_fixture, request):
    result = _run(request.getfixturevalue(uri_fixture))
    assert result["codes"] == [200, 200, 429]
    assert result["elapsed"] < 3
