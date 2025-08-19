from flask import request, jsonify, Response

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.auth_utils import resolve_owner_id_from_request
from builders import UrlListQueryBuilder

from . import api_v1


@api_v1.route("/urls", methods=["GET"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="60 per minute; 5000 per day",
        anonymous="0 per minute",  # Requires authentication
    ),
    key_func=rate_limit_key_for_request,
)
def list_urls_v1() -> tuple[Response, int]:
    owner_id = resolve_owner_id_from_request()
    if owner_id is None:
        return jsonify({"error": "authentication required"}), 401

    builder = (
        UrlListQueryBuilder(owner_id, request.args)
        .parse_auth_scope()
        .parse_pagination()
        .parse_sort()
        .parse_filters()
    )
    return builder.build()
