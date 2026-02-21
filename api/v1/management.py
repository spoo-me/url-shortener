from flask import request, jsonify, Response
from bson import ObjectId

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.mongo_utils import urls_v2_collection
from utils.logger import get_logger
from builders import UpdateUrlRequestBuilder
from cache import cache_query as cq

from . import api_v1

log = get_logger(__name__)


@api_v1.route("/urls/<url_id>", methods=["PATCH"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="120 per minute; 2000 per day",
        anonymous="0 per minute",  # Requires authentication
    ),
    key_func=rate_limit_key_for_request,
)
def update_url_v1(url_id: str) -> tuple[Response, int]:
    """
    Update an existing shortened URL's properties.

    This endpoint allows authenticated users to modify properties of URLs they own,
    including the destination, alias, password, expiration, and other settings.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **API Key** (required): Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes**: `urls:manage` or `admin:all`
    - **Ownership**: Can only update URLs you own
    - **Rate Limits**: 120/min & 2000/day (auth), Anonymous: Disabled

    ## URL Parameters
    - **url_id** (string): MongoDB ObjectId of the URL to update

    ## Request Body (JSON)
    All fields are optional - only include fields you want to update.

    ### Optional Fields
    - **long_url** (string): New destination URL
      - Must start with http:// or https://
      - Maximum length: 2048 characters
    - **alias** (string): New custom short code
      - 16 characters max, auto truncated if longer
      - Alphanumeric, hyphens, and underscores only
      - Must be unique (returns 409 if taken)
      - Cannot change to existing alias
    - **password** (string | null): Update or remove password
      - Atleast 8 characters long, must contain a letter and a number and a special character either '@' or '.' and cannot be consecutive
      - Set to `null` or empty string to remove
    - **max_clicks** (integer | null): Update or remove click limit
      - Must be positive integer to set
      - Set to `null` to remove limit
    - **expire_after** (integer | null): Update or remove expiration
      - Unix epoch seconds (must be in future)
      - Set to `null` to remove expiration
    - **block_bots** (boolean | null): Update or remove bot blocking
      - Set to `null` to remove
    - **private_stats** (boolean | null): Update or remove stats privacy
      - Set to `null` to remove
    - **status** (string): Change URL status
      - Values: "ACTIVE" or "INACTIVE"

    ## Example Request
    ```json
    {
      "long_url": "https://example.com/new-destination",
      "max_clicks": 500,
      "password": null,
      "private_stats": true
    }
    ```

    ## Response Format
    ```json
    {
      "id": "507f1f77bcf86cd799439011",
      "alias": "mylink",
      "long_url": "https://example.com/new-destination",
      "status": "ACTIVE",
      "password_set": false,
      "max_clicks": 500,
      "expire_after": null,
      "block_bots": false,
      "private_stats": true,
      "updated_at": 1704067200
    }
    ```

    ## Special Responses
    - **200**: Successfully updated (or no changes detected)
    - **400**: Invalid URL ID format, invalid field values
    - **401**: Authentication required, invalid token
    - **403**: Access denied (not the owner), insufficient scope
    - **404**: URL not found
    - **409**: New alias already taken
    - **429**: Rate limit exceeded
    - **500**: Database/server error

    Returns:
        tuple[Response, int]: JSON response with updated URL data and HTTP status code
    """
    payload = request.get_json(silent=True) or {}

    builder = (
        UpdateUrlRequestBuilder(payload, url_id)
        .parse_auth_scope(required_scopes={"urls:manage", "admin:all"})
        .load_and_validate_ownership()
        .validate_long_url_if_present()
        .validate_alias_custom()
        .validate_password()
        .parse_max_clicks()
        .parse_expire_after()
        .parse_block_bots()
        .parse_private_stats()
    )

    return builder.build_update()


@api_v1.route("/urls/<url_id>/status", methods=["PATCH"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="120 per minute; 2000 per day",
        anonymous="0 per minute",  # Requires authentication
    ),
    key_func=rate_limit_key_for_request,
)
def update_url_status_v1(url_id: str) -> tuple[Response, int]:
    """
    Update only the status of a shortened URL (ACTIVE/INACTIVE).

    This is a convenience endpoint for quickly enabling or disabling a URL
    without modifying any other properties. Only status changes are allowed.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **API Key** (required): Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes**: `urls:manage` or `admin:all`
    - **Ownership**: Can only update URLs you own
    - **Rate Limits**: 120/min & 2000/day (auth), Anonymous: Disabled

    ## URL Parameters
    - **url_id** (string): MongoDB ObjectId of the URL to update

    ## Request Body (JSON)

    ### Required
    - **status** (string): New status for the URL
      - Values: "ACTIVE" or "INACTIVE"
      - "ACTIVE": URL is accessible and redirects normally
      - "INACTIVE": URL is disabled and won't redirect

    ## Example Request
    ```json
    {
      "status": "INACTIVE"
    }
    ```

    ## Response Format
    ```json
    {
      "id": "507f1f77bcf86cd799439011",
      "alias": "mylink",
      "long_url": "https://example.com/destination",
      "status": "INACTIVE",
      "password_set": true,
      "max_clicks": 100,
      "expire_after": 1735689600,
      "block_bots": false,
      "private_stats": false,
      "updated_at": 1704067200
    }
    ```

    ## Error Responses
    - **400**: Invalid URL ID format, invalid status value
    - **401**: Authentication required, invalid token
    - **403**: Access denied (not the owner), insufficient scope
    - **404**: URL not found
    - **429**: Rate limit exceeded
    - **500**: Database/server error

    Returns:
        tuple[Response, int]: JSON response with updated URL data and HTTP status code
    """
    payload = request.get_json(silent=True) or {}

    # Only allow status changes
    filtered_payload = {"status": payload.get("status")}

    builder = (
        UpdateUrlRequestBuilder(filtered_payload, url_id)
        .parse_auth_scope(required_scopes={"urls:manage", "admin:all"})
        .load_and_validate_ownership()
        .parse_status_change()
    )

    return builder.build_update()


@api_v1.route("/urls/<url_id>", methods=["DELETE"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="60 per minute; 1000 per day",
        anonymous="0 per minute",  # Requires authentication
    ),
    key_func=rate_limit_key_for_request,
)
def delete_url_v1(url_id: str) -> tuple[Response, int]:
    """
    Permanently delete a shortened URL from the database.

    This endpoint removes a URL completely from the system. This action is
    irreversible - all associated data including analytics will be permanently lost.
    The short alias becomes available for reuse after deletion.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **API Key** (required): Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes**: `urls:manage` or `admin:all`
    - **Ownership**: Can only delete URLs you own
    - **Rate Limits**: 60/min & 1000/day (auth), Anonymous: Disabled

    ## URL Parameters
    - **url_id** (string): MongoDB ObjectId of the URL to delete

    ## Request Body
    No request body required.

    ## Response Format
    ```json
    {
      "message": "URL deleted",
      "id": "507f1f77bcf86cd799439011"
    }
    ```

    ## Error Responses
    - **400**: Invalid URL ID format
    - **401**: Authentication required, invalid token
    - **403**: Access denied (not the owner), insufficient scope
    - **404**: URL not found or already deleted
    - **429**: Rate limit exceeded
    - **500**: Database/server error

    ## Important Notes
    - **Irreversible**: Deletion cannot be undone
    - **Data Loss**: All analytics and click data will be lost
    - **Cache**: The system automatically invalidates the cache for the deleted URL
    - **Alias Reuse**: The deleted alias becomes available for new URLs

    ## Alternative
    Consider using `PATCH /api/v1/urls/<url_id>/status` to set status to "INACTIVE"
    instead of deleting, which preserves data while disabling the URL.

    Returns:
        tuple[Response, int]: JSON response confirming deletion and HTTP status code (200 on success)
    """
    try:
        url_oid = ObjectId(url_id)
    except Exception:
        return jsonify({"error": "Invalid URL ID format"}), 400

    # Validate ownership first
    builder = (
        UpdateUrlRequestBuilder({}, url_id)
        .parse_auth_scope(required_scopes={"urls:manage", "admin:all"})
        .load_and_validate_ownership()
    )

    if builder.error:
        return builder.error

    # Get the alias/short_code before deletion for cache invalidation
    url_doc = builder.existing_doc
    short_code = url_doc.get("alias") if url_doc else None

    try:
        result = urls_v2_collection.delete_one({"_id": url_oid})
        if result.deleted_count == 0:
            return jsonify({"error": "URL not found"}), 404

        log.info(
            "url_deleted",
            url_id=url_id,
            alias=short_code,
            owner_id=str(builder.owner_id) if builder.owner_id else None,
        )

        # Invalidate cache after successful deletion
        if short_code:
            try:
                cq.invalidate_url_cache(short_code=short_code)
            except Exception as e:
                log.error(
                    "cache_invalidation_failed",
                    short_code=short_code,
                    reason="post_deletion",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        return jsonify({"message": "URL deleted", "id": url_id}), 200

    except Exception as e:
        log.error(
            "url_deletion_failed",
            url_id=url_id,
            alias=short_code,
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": "Database error"}), 500
