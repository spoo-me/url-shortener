from flask import request, Response

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.auth_utils import resolve_owner_id_from_request
from builders import StatsQueryBuilder

from . import api_v1


@api_v1.route("/stats", methods=["GET"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="60 per minute; 5000 per day",
        anonymous="20 per minute; 1000 per day",
    ),
    key_func=rate_limit_key_for_request,
)
def stats_v1() -> tuple[Response, int]:
    """
    Get URL click statistics with flexible filtering, grouping, and aggregation.

    This endpoint provides comprehensive analytics for shortened URLs with support for
    different scopes, time ranges, dimensional grouping, and privacy controls.

    ## Authentication & Authorization
    - **JWT Token**: Use `Authorization: Bearer <jwt_token>` header
    - **API Key**: Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes**: `stats:read`, `urls:read`, or `admin:all`
    - **Rate Limits**: 60/min (auth), 20/min (anon)

    ## Query Parameters

    ### Required
    - **scope** (string): Statistics scope
      - `"all"` - All URLs owned by authenticated user
      - `"url"` - Single URL (requires `url_id` + auth + ownership)
      - `"anon"` - Anonymous access (requires `short_code` + public stats)

    ### Conditional
    - **url_id** (string): MongoDB ObjectId (required for `scope=url`)
    - **short_code** (string): URL alias (required for `scope=anon`)

    ### Optional
    - **start_date** (string): ISO 8601 or Unix timestamp (default: 7 days ago)
    - **end_date** (string): ISO 8601 or Unix timestamp (default: now)
    - **timezone** (string): IANA timezone for output formatting (default: "UTC")
      - Examples: "America/New_York", "Europe/London", "Asia/Kolkata"
      - Affects only output display (summary timestamps, time buckets, metadata)
      - Does not affect data fetching or aggregation logic
    - **group_by** (string): Comma-separated dimensions (default: "time")
      - Options: time, browser, os, device, country, city, referrer, key
    - **metrics** (string): Comma-separated metrics (default: "clicks,unique_clicks")
      - Options: clicks, unique_clicks
    - **filters** (JSON string): Dimension filters
      - Example: `{"browser": ["Chrome", "Firefox"], "country": ["US", "UK"]}`
    - **browser, os, device, country, referrer** (string): Individual filters

    ## Response Format
    ```json
    {
      "scope": "all",
      "timezone": "America/New_York",
      "group_by": ["time"],
      "time_range": {
        "start_date": "2024-12-31T19:00:00-05:00",
        "end_date": "2025-01-07T19:00:00-05:00"
      },
      "summary": {
        "total_clicks": 150,
        "unique_clicks": 89,
        "first_click": "2025-01-01T05:30:00-05:00",
        "last_click": "2025-01-07T13:45:00-05:00",
        "avg_redirection_time": 142.35
      },
      "metrics": {
        "clicks_by_time": [
          {"time": "2024-12-31", "clicks": 25},
          {"time": "2025-01-01", "clicks": 18}
        ],
        "unique_clicks_by_time": [
          {"time": "2024-12-31", "unique_clicks": 20},
          {"time": "2025-01-01", "unique_clicks": 15}
        ]
      },
      "time_bucket_info": {
        "strategy": "daily",
        "timezone": "America/New_York"
      }
    }
    ```

    ## Error Responses
    - **400**: Invalid parameters, missing required fields
    - **401**: Authentication required, invalid token
    - **403**: Insufficient permissions, private statistics, access denied
    - **404**: URL/short_code not found, ownership validation failed
    - **429**: Rate limit exceeded
    - **500**: Database/server error

    Returns:
        tuple[Response, int]: JSON response with statistics data and HTTP status code
    """
    owner_id = resolve_owner_id_from_request()

    builder: StatsQueryBuilder = (
        StatsQueryBuilder(owner_id, request.args)
        .parse_auth_scope()
        .parse_scope_and_target()
        .parse_time_range()
        .parse_filters()
        .parse_group_by()
        .parse_metrics()
        .parse_timezone()
    )
    return builder.build()
