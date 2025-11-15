from flask import request, jsonify, g
from datetime import datetime, timezone
import secrets
import hashlib
from typing import Optional

from utils.auth_utils import requires_auth
from utils.logger import get_logger
from bson import ObjectId
from utils.mongo_utils import (
    insert_api_key,
    list_api_keys_by_user,
    revoke_api_key_by_id,
)
from blueprints.limiter import limiter, rate_limit_key_for_request

from . import api_v1

log = get_logger(__name__)


ALLOWED_SCOPES = {
    "shorten:create",
    "urls:manage",
    "urls:read",
    "stats:read",
    "admin:all",
}


def _parse_expires_at(value: Optional[str | int | float]):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


@api_v1.route("/keys", methods=["POST"])
@limiter.limit("5 per hour", key_func=rate_limit_key_for_request)
@requires_auth
def create_api_key():
    """
    Create a new API key for programmatic access.

    This endpoint allows authenticated users to generate API keys for accessing the
    spoo.me API programmatically. API keys can be scoped with specific permissions
    and optionally set to expire after a certain time.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **Rate Limits**: 5 per hour (to prevent abuse)
    - **Limit**: Maximum 20 active keys per user

    ## Request Body (JSON)

    ### Required
    - **name** (string): Human-readable name for the key
      - Cannot be empty or whitespace-only
      - Used to identify the key in lists
    - **scopes** (array of strings): Permissions granted to this key
      - Must be a non-empty array
      - Available scopes:
        - `shorten:create` - Create new shortened URLs
        - `urls:manage` - Update and delete URLs
        - `urls:read` - List and view URL details
        - `stats:read` - Access analytics and statistics
        - `admin:all` - Full administrative access

    ### Optional
    - **description** (string): Detailed description of the key's purpose
      - Can be null or empty
    - **expires_at** (string | integer): When the key should expire
      - ISO 8601 datetime string or Unix epoch seconds
      - Must be in the future
      - Set to null for no expiration

    ## Example Request
    ```json
    {
      "name": "Production API Key",
      "description": "API key for production deployment",
      "scopes": ["shorten:create", "urls:read", "stats:read"],
      "expires_at": "2025-12-31T23:59:59Z"
    }
    ```

    ## Response Format
    ```json
    {
      "id": "507f1f77bcf86cd799439011",
      "name": "Production API Key",
      "description": "API key for production deployment",
      "scopes": ["shorten:create", "urls:read", "stats:read"],
      "created_at": 1704067200,
      "expires_at": 1735689599,
      "revoked": false,
      "token_prefix": "AbCdEfGh",
      "token": "spoo_AbCdEfGhIjKlMnOpQrStUvWxYzAbCdEfGhIjKlMn"
    }
    ```

    ## Response Fields
    - **token**: The full API key (shown ONLY once at creation)
      - Format: `spoo_<random_string>`
      - Store securely - cannot be retrieved later
      - Use in `Authorization: Bearer <token>` header
    - **token_prefix**: First 8 characters of the key (for identification)
    - **id**: Unique identifier for this key
    - **created_at**: Unix timestamp of creation
    - **expires_at**: Unix timestamp of expiration (null if none)
    - **revoked**: Whether the key has been revoked

    ## Error Responses
    - **400**: Missing/invalid name, empty/invalid scopes, invalid expiration date
    - **400**: Maximum 20 active keys reached
    - **401**: Authentication required, invalid JWT token
    - **403**: Email verification required
    - **429**: Rate limit exceeded (5 per hour)
    - **500**: Failed to create API key, database error

    ## Important Notes
    - **One-time display**: The full token is shown ONLY at creation
    - **Store securely**: Save the token immediately - it cannot be retrieved later
    - **Token format**: Always starts with `spoo_` prefix
    - **Security**: Tokens are hashed (SHA-256) before storage
    - **Key limit**: Users can have maximum 20 active (non-revoked) keys

    Returns:
        tuple[Response, int]: JSON response with API key data and HTTP status code (201 on success)
    """
    # Check email verification for API key creation
    if not g.jwt_claims.get("email_verified", False):
        log.warning(
            "api_key_creation_blocked",
            reason="email_not_verified",
            user_id=str(g.user_id),
        )
        return (
            jsonify(
                {
                    "error": "Email verification required",
                    "code": "EMAIL_NOT_VERIFIED",
                    "message": "You must verify your email address before creating API keys. Check your inbox for the verification code.",
                }
            ),
            403,
        )

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip() or None
    scopes = body.get("scopes") or []
    expires_at_raw = body.get("expires_at")

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not isinstance(scopes, list) or not scopes:
        return jsonify({"error": "scopes must be a non-empty array"}), 400
    if any(scope not in ALLOWED_SCOPES for scope in scopes):
        return jsonify({"error": "invalid scope requested"}), 400

    # Check if user has too many active keys (prevent abuse)
    existing_keys = list_api_keys_by_user(g.user_id, projection={"revoked": 1})
    active_keys = [k for k in existing_keys if not k.get("revoked", False)]

    MAX_ACTIVE_KEYS = 20
    if len(active_keys) >= MAX_ACTIVE_KEYS:
        return jsonify({"error": f"maximum {MAX_ACTIVE_KEYS} active keys allowed"}), 400

    expires_at = _parse_expires_at(expires_at_raw)
    if expires_at_raw is not None and expires_at is None:
        return jsonify({"error": "expires_at must be ISO8601 or epoch seconds"}), 400
    if expires_at and expires_at <= datetime.now(timezone.utc):
        return jsonify({"error": "expires_at must be in the future"}), 400

    # Generate key
    raw = secrets.token_urlsafe(32)
    token_prefix = raw[:8]
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    user_oid = ObjectId(g.user_id) if not isinstance(g.user_id, ObjectId) else g.user_id
    doc = {
        "user_id": user_oid,
        "token_prefix": token_prefix,
        "token_hash": token_hash,
        "name": name,
        "description": description,
        "scopes": scopes,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
        "revoked": False,
    }

    key_id = insert_api_key(doc)
    if not key_id:
        log.error(
            "api_key_creation_failed",
            user_id=str(g.user_id),
            scopes=scopes,
            error="database_error",
        )
        return jsonify({"error": "failed to create api key"}), 500

    log.info(
        "api_key_created",
        user_id=str(g.user_id),
        key_id=str(key_id),
        key_prefix=token_prefix,
        scopes=scopes,
        expires_at=expires_at.isoformat() if expires_at else None,
    )

    return (
        jsonify(
            {
                "id": str(key_id),
                "name": name,
                "description": description,
                "scopes": scopes,
                "created_at": int(doc["created_at"].timestamp()),
                "expires_at": int(expires_at.timestamp()) if expires_at else None,
                "revoked": False,
                "token_prefix": token_prefix,
                "token": f"spoo_{raw}",
            }
        ),
        201,
    )


@api_v1.route("/keys", methods=["GET"])
@limiter.limit("60 per minute", key_func=rate_limit_key_for_request)
@requires_auth
def list_api_keys():
    """
    List all API keys for the authenticated user.

    This endpoint returns all API keys (both active and revoked) created by the
    authenticated user. For security, only the token prefix is returned, not the
    full token value.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **Rate Limits**: 60 per minute

    ## Query Parameters
    No query parameters required.

    ## Response Format
    ```json
    {
      "keys": [
        {
          "id": "507f1f77bcf86cd799439011",
          "name": "Production API Key",
          "description": "API key for production deployment",
          "scopes": ["shorten:create", "urls:read", "stats:read"],
          "created_at": 1704067200,
          "expires_at": 1735689599,
          "revoked": false,
          "token_prefix": "AbCdEfGh"
        },
        {
          "id": "507f1f77bcf86cd799439012",
          "name": "Old Testing Key",
          "description": null,
          "scopes": ["shorten:create"],
          "created_at": 1700000000,
          "expires_at": null,
          "revoked": true,
          "token_prefix": "XyZaBcDe"
        }
      ]
    }
    ```

    ## Response Fields
    - **keys**: Array of API key objects
      - **id**: Unique identifier for the key
      - **name**: Human-readable name
      - **description**: Optional description (can be null)
      - **scopes**: Array of permission scopes
      - **created_at**: Unix timestamp of creation
      - **expires_at**: Unix timestamp of expiration (null if none)
      - **revoked**: Boolean indicating if key is revoked
      - **token_prefix**: First 8 characters (for identification)

    ## Key Status Interpretation
    - **Active**: `revoked: false` and (`expires_at: null` or `expires_at` in future)
    - **Revoked**: `revoked: true`
    - **Expired**: `expires_at` in the past

    ## Error Responses
    - **401**: Authentication required, invalid JWT token
    - **429**: Rate limit exceeded
    - **500**: Database error

    ## Important Notes
    - **No full tokens**: For security, full tokens are never returned
    - **All keys shown**: Both active and revoked keys are included
    - **Token prefix**: Use to identify which key is which
    - **Security**: Check the `revoked` and `expires_at` fields to verify key status

    Returns:
        tuple[Response, int]: JSON response with list of API keys and HTTP status code
    """
    keys = list_api_keys_by_user(g.user_id)
    result = []
    for k in keys:
        result.append(
            {
                "id": str(k["_id"]),
                "name": k.get("name"),
                "description": k.get("description"),
                "scopes": k.get("scopes", []),
                "created_at": int(k.get("created_at").timestamp())
                if k.get("created_at")
                else None,
                "expires_at": int(k.get("expires_at").timestamp())
                if k.get("expires_at")
                else None,
                "revoked": bool(k.get("revoked", False)),
                "token_prefix": k.get("token_prefix"),
            }
        )
    return jsonify({"keys": result})


@api_v1.route("/keys/<key_id>", methods=["DELETE"])
@requires_auth
def delete_api_key(key_id):
    """
    Delete or revoke an API key.

    This endpoint allows users to remove an API key. By default, keys are permanently
    deleted (hard delete), but you can optionally just revoke them to preserve audit logs.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **Ownership**: Can only delete/revoke your own API keys

    ## URL Parameters
    - **key_id** (string): MongoDB ObjectId of the API key

    ## Query Parameters
    - **revoke** (boolean): If "true", revoke instead of delete (default: "false")
      - `?revoke=true` - Marks key as revoked but keeps record
      - Default behavior - Permanently deletes the key

    ## Behavior Modes

    ### Hard Delete (Default)
    ```
    DELETE /api/v1/keys/507f1f77bcf86cd799439011
    ```
    - Permanently removes the key from database
    - No audit trail preserved
    - Key ID becomes invalid
    - Recommended for unused/test keys

    ### Soft Delete (Revoke)
    ```
    DELETE /api/v1/keys/507f1f77bcf86cd799439011?revoke=true
    ```
    - Marks key as `revoked: true`
    - Preserves key record for audit purposes
    - Key still appears in list but cannot be used
    - Recommended for production keys

    ## Response Format
    ```json
    {
      "success": true,
      "action": "deleted"
    }
    ```
    or
    ```json
    {
      "success": true,
      "action": "revoked"
    }
    ```

    ## Error Responses
    - **401**: Authentication required, invalid JWT token
    - **404**: Key not found, access denied (not your key), invalid key ID
    - **500**: Database error

    ## Important Notes
    - **Immediate effect**: Key stops working immediately
    - **No confirmation**: Action is performed without confirmation prompt
    - **Irreversible**: Hard deletes cannot be undone
    - **Ownership**: Can only delete your own keys
    - **Revoke vs Delete**: Use revoke for audit trails, delete for cleanup

    ## Use Cases
    - **Delete**: Removing test keys, cleaning up unused keys
    - **Revoke**: Disabling production keys while preserving history
    - **Security**: Immediately disable compromised keys

    Returns:
        tuple[Response, int]: JSON response confirming action and HTTP status code
    """
    # Default to hard delete for cleaner UX, use ?revoke=true to just revoke
    revoke_only = (request.args.get("revoke") or "false").lower() == "true"
    ok = revoke_api_key_by_id(g.user_id, key_id, hard_delete=not revoke_only)
    if not ok:
        log.warning(
            "api_key_deletion_failed",
            user_id=str(g.user_id),
            key_id=key_id,
            action="revoke" if revoke_only else "delete",
            reason="not_found_or_access_denied",
        )
        return jsonify({"error": "key not found or access denied"}), 404

    action = "revoked" if revoke_only else "deleted"
    log.info(
        "api_key_revoked" if revoke_only else "api_key_deleted",
        user_id=str(g.user_id),
        key_id=key_id,
        action=action,
    )

    return jsonify({"success": True, "action": action})
