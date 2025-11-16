from flask import request, Response

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.mongo_utils import urls_v2_collection
from builders import ShortenRequestBuilder

from . import api_v1


@api_v1.route("/shorten", methods=["POST"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="60 per minute; 5000 per day",
        anonymous="20 per minute; 1000 per day",
    ),
    key_func=rate_limit_key_for_request,
)
def shorten_v1() -> tuple[Response, int]:
    """
    Create a new shortened URL.

    This endpoint creates a shortened URL with optional customization including
    password protection, expiration, click limits, and bot blocking.

    ## Authentication & Authorization
    - **JWT Token** (optional): Use `Authorization: Bearer <jwt_token>` header
    - **API Key** (optional): Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes** (if authenticated): `shorten:create` or `admin:all`
    - **Rate Limits**: 60/min & 5000/day (auth), 20/min & 1000/day (anon)

    ## Request Body (JSON)

    ### Required
    - **long_url** (string): The original URL to shorten
        - Must start with http:// or https://
        - Maximum length: 2048 characters
        - Must be a valid, accessible URL

    ### Optional
    - **alias** (string): Custom short code/alias for the URL
        - 16 characters max, auto truncated if longer
        - Alphanumeric, hyphens, and underscores only
        - Must be unique (returns 409 if taken)
        - Auto-generated if not provided
    - **password** (string): Password to protect the shortened URL
        - Minimum 4 characters
        - Stored as bcrypt hash
        - Required when accessing the shortened URL
    - **max_clicks** (integer): Maximum number of clicks allowed
        - Must be positive integer
        - URL becomes inactive after limit reached
        - Set to `null` or omit for unlimited clicks
    - **expire_after** (integer): Expiration timestamp (Unix epoch seconds)
        - Must be in the future
        - URL becomes inactive after this time
        - Set to `null` or omit for no expiration
    - **block_bots** (boolean): Block known bot user agents
        - Default: `false`
        - When `true`, blocks automated traffic
    - **private_stats** (boolean): Make statistics private
        - Default: `false`
        - When `true`, only owner can view stats

    ## Example Request
    ```json
    {
        "long_url": "https://example.com/very/long/url",
        "alias": "mylink",
        "password": "secure123",
        "max_clicks": 100,
        "expire_after": 1735689600,
        "block_bots": true,
        "private_stats": false
    }
    ```

    ## Response Format
    ```json
    {
        "alias": "mylink",
        "short_url": "https://spoo.me/mylink",
        "long_url": "https://example.com/very/long/url",
        "owner_id": "507f1f77bcf86cd799439011",
        "created_at": 1704067200,
        "status": "ACTIVE",
        "private_stats": false
    }
    ```

    ## Error Responses
    - **400**: Invalid request body, missing required fields, invalid URL format
    - **401**: Authentication required (if invalid token provided)
    - **403**: Insufficient permissions (missing required scope)
    - **409**: Alias already taken
    - **429**: Rate limit exceeded
    - **500**: Database/server error

    Returns:
        tuple[Response, int]: JSON response with shortened URL data and HTTP status code (201 on success)
    """
    payload = request.get_json(silent=True) or {}

    builder = (
        ShortenRequestBuilder(payload)
        .parse_auth_scope(required_scopes={"shorten:create", "admin:all"})
        .validate_long_url()
        .validate_or_generate_alias()
        .validate_password()
        .parse_block_bots()
        .parse_max_clicks()
        .parse_expire_after()
        .parse_private_stats()
    )
    return builder.build(collection=urls_v2_collection)
