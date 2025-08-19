from flask import request, jsonify, Response
from bson import ObjectId

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.mongo_utils import urls_v2_collection
from builders import UpdateUrlRequestBuilder

from . import api_v1


@api_v1.route("/urls/<url_id>", methods=["PATCH"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="120 per minute; 2000 per day",
        anonymous="0 per minute",  # Requires authentication
    ),
    key_func=rate_limit_key_for_request,
)
def update_url_v1(url_id: str) -> tuple[Response, int]:
    """Update an existing URL's properties"""
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
    """Update only the status of a URL (ACTIVE/INACTIVE)"""
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
    """Delete a URL (permanently removes it from the database)"""
    try:
        url_oid = ObjectId(url_id)
    except Exception:
        return jsonify({"error": "Invalid URL ID format"}), 400

    # Validate ownership first
    builder = UpdateUrlRequestBuilder({}, url_id)
    builder.parse_auth_scope(required_scopes={"urls:manage", "admin:all"})
    builder.load_and_validate_ownership()

    if builder.error:
        return builder.error

    try:
        result = urls_v2_collection.delete_one({"_id": url_oid})
        if result.deleted_count == 0:
            return jsonify({"error": "URL not found"}), 404

        return jsonify({"message": "URL deleted", "id": url_id}), 200

    except Exception:
        return jsonify({"error": "Database error"}), 500
