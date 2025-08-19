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
