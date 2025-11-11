from flask_limiter import Limiter
from utils.mongo_utils import MONGO_URI, ip_bypasses
from utils.url_utils import get_client_ip
from utils.logger import get_logger
from flask import request
from utils.auth_utils import resolve_owner_id_from_request

log = get_logger(__name__)

limiter = Limiter(
    key_func=get_client_ip,  # Use custom function that handles Cloudflare/proxy headers
    default_limits=["10 per minute", "500 per day", "100 per hour"],
    storage_uri=MONGO_URI,
    strategy="fixed-window",
    headers_enabled=True,
)


@limiter.request_filter
def ip_whitelist():
    """Skip rate limiting for whitelisted IPs"""
    bypasses = ip_bypasses.find()
    bypasses = [doc["_id"] for doc in bypasses]

    client_ip = get_client_ip()
    return client_ip in bypasses


def dynamic_limit_for_request(
    *,
    authenticated: str = "60 per minute; 5000 per day",
    anonymous: str = "20 per minute; 1000 per day",
) -> str:
    """Higher limits for authenticated/API-key users, lower for anonymous.

    You can override the defaults per-endpoint by calling this with custom values:
    dynamic_limit_for_request(authenticated="120 per minute", anonymous="30 per minute")
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
            return f"apikey:{token[:20]}"
    return get_client_ip()
