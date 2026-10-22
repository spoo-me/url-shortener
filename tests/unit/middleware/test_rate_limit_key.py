"""rate_limit_key: only verified credentials get their own bucket."""

from __future__ import annotations

import hashlib

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.middleware.rate_limiter import limiter, rate_limit_key


def _request(headers: dict[str, str], auth_ctx: dict | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw,
        "client": ("10.0.0.9", 1234),
        "state": {},
    }
    request = Request(scope)
    if auth_ctx is not None:
        request.state.auth_ctx = auth_ctx
    return request


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def test_unverified_bearer_is_keyed_by_ip():
    request = _request({"Authorization": "Bearer junk", "CF-Connecting-IP": "1.2.3.4"})
    assert rate_limit_key(request) == "1.2.3.4"


def test_unverified_api_key_is_keyed_by_ip():
    request = _request(
        {"Authorization": "Bearer spoo_junk", "CF-Connecting-IP": "1.2.3.4"}
    )
    assert rate_limit_key(request) == "1.2.3.4"


def test_unverified_cookie_is_keyed_by_ip():
    request = _request({"Cookie": "access_token=junk", "CF-Connecting-IP": "1.2.3.4"})
    assert rate_limit_key(request) == "1.2.3.4"


def test_verified_api_key_keeps_its_own_bucket():
    request = _request(
        {"Authorization": "Bearer spoo_real", "CF-Connecting-IP": "1.2.3.4"},
        auth_ctx={"user_id": "u", "auth_method": "api_key"},
    )
    assert rate_limit_key(request) == f"apikey:{_hash('spoo_real')}"


def test_verified_jwt_keeps_its_own_bucket():
    request = _request(
        {"Authorization": "Bearer eyJ.real", "CF-Connecting-IP": "1.2.3.4"},
        auth_ctx={"user_id": "u", "auth_method": "jwt"},
    )
    assert rate_limit_key(request) == f"jwt:{_hash('eyJ.real')}"


def test_random_tokens_do_not_bypass_a_public_route_limit():
    limiter.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.post("/login-like")
    @limiter.limit("3 per minute")
    async def login_like(request: Request):
        return {"ok": True}

    with TestClient(app) as client:
        statuses = [
            client.post(
                "/login-like",
                headers={
                    "Authorization": f"Bearer junk{i}",
                    "CF-Connecting-IP": "5.6.7.8",
                },
            ).status_code
            for i in range(6)
        ]
    limiter.reset()
    assert statuses == [200, 200, 200, 429, 429, 429]
