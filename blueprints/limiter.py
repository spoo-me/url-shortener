import os
import hashlib
from flask_limiter import Limiter
from flask import request
from utils.mongo_utils import MONGO_URI, ip_bypasses
from utils.url_utils import get_client_ip
from utils.logger import get_logger
from utils.auth_utils import resolve_owner_id_from_request
from cache import cache_store
from .limits import Limits

log = get_logger(__name__)

# Use Redis for rate limit counters (atomic INCR/EXPIRE, sub-millisecond).
# Fall back to MongoDB if REDIS_URI is not configured.
_redis_uri = os.environ.get("REDIS_URI")
_storage_uri = _redis_uri if _redis_uri else MONGO_URI

limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[Limits.DEFAULT_MINUTE, Limits.DEFAULT_HOUR, Limits.DEFAULT_DAY],
    storage_uri=_storage_uri,
    strategy="fixed-window",
    headers_enabled=True,
)


@cache_store.cached(key="cache:ip_bypasses", ttl=120)
def _get_ip_bypasses() -> list:
    return [doc["_id"] for doc in ip_bypasses.find()]


@limiter.request_filter
def ip_whitelist():
    """Skip rate limiting for whitelisted IPs"""
    client_ip = get_client_ip()
    return client_ip in _get_ip_bypasses()


def dynamic_limit_for_request(
    *,
    authenticated: str = Limits.API_AUTHED,
    anonymous: str = Limits.API_ANON,
) -> str:
    """Higher limits for authenticated/API-key users, lower for anonymous.

    You can override the defaults per-endpoint by calling this with custom values:
    dynamic_limit_for_request(authenticated=Limits.X, anonymous=Limits.Y)
    """
    owner_id = resolve_owner_id_from_request()
    if owner_id is not None:
        return authenticated
    return anonymous


def rate_limit_key_for_request() -> str:
    """Bucket by user id when authenticated, else by API key prefix if provided, else IP."""
    owner_id = resolve_owner_id_from_request()
    if owner_id is not None:
        return f"user:{str(owner_id)}"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token.startswith("spoo_"):
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            return f"apikey:{token_hash}"
    return get_client_ip()
