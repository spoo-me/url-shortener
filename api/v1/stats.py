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
      - `"all"` - All URLs owned by authenticated user (requires authentication)
      - `"anon"` - Anonymous access to single URL (requires `short_code` + public stats)

    ### Conditional
    - **short_code** (string): URL alias (required for `scope=anon`)
      - Cannot use `short_code` filter when `scope=anon` (security measure)

    ### Optional - Time Range
    - **start_date** (string): ISO 8601 datetime or Unix timestamp
      - Default: 7 days before `end_date` (or 7 days ago if no `end_date`)
      - Future dates capped to current time
      - Examples: "2024-01-01T00:00:00Z" or 1704067200
    - **end_date** (string): ISO 8601 datetime or Unix timestamp
      - Default: Current time
      - Future dates capped to current time
      - Examples: "2024-12-31T23:59:59Z" or 1735689599
    - **timezone** (string): IANA timezone for output formatting (default: "UTC")
      - Converts all timestamps in response to specified timezone
      - Examples: "America/New_York", "Europe/London", "Asia/Kolkata"
      - Supports timezone aliases (e.g., "US/Eastern" → "America/New_York")
      - Invalid timezones fallback to "UTC"

    ### Optional - Grouping & Metrics
    - **group_by** (string): Comma-separated dimensions (default: "time")
      - Available: `time`, `browser`, `os`, `country`, `city`, `referrer`, `short_code`
      - Note: `device` dimension is currently disabled (reliable detection not available)
      - Example: `?group_by=time,country,browser`
    - **metrics** (string): Comma-separated metrics (default: "clicks,unique_clicks")
      - Available: `clicks`, `unique_clicks`
      - Example: `?metrics=clicks` or `?metrics=clicks,unique_clicks`

    ### Optional - Filtering
    You can filter by dimensions in two ways (both can be combined):

    #### Method 1: JSON filters parameter
    - **filters** (JSON string): Structured dimension filters
      - Format: `{"dimension": ["value1", "value2"]}`
      - Available dimensions: `browser`, `os`, `country`, `city`, `referrer`, `short_code`
      - Note: `device` filter disabled (reliable detection not available)
      - Example: `?filters={"browser":["Chrome","Firefox"],"country":["US","CA"]}`

    #### Method 2: Individual filter parameters
    - **browser** (string): Comma-separated browser names
    - **os** (string): Comma-separated OS names
    - **country** (string): Comma-separated country codes
    - **city** (string): Comma-separated city names
    - **referrer** (string): Comma-separated referrer URLs
    - **short_code** (string): Comma-separated URL aliases (not allowed with `scope=anon`)
    - Example: `?browser=Chrome,Firefox&country=US,CA`

    ## Response Format
    ```json
    {
      "scope": "all",
      "timezone": "America/New_York",
      "group_by": ["time"],
      "filters": {},
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

    ## Response Fields
    - **scope**: Echo of the requested scope (`all` or `anon`)
    - **timezone**: IANA timezone used for formatting (all timestamps use this)
    - **group_by**: Array of dimensions used for grouping
    - **filters**: Applied dimension filters (empty object if none)
    - **time_range**: Query time window
      - **start_date**: ISO 8601 datetime in specified timezone
      - **end_date**: ISO 8601 datetime in specified timezone
    - **summary**: Aggregate statistics across all data
      - **total_clicks**: Total number of clicks
      - **unique_clicks**: Count of unique IP addresses
      - **first_click**: Timestamp of first click (in specified timezone)
      - **last_click**: Timestamp of last click (in specified timezone)
      - **avg_redirection_time**: Average redirect time in milliseconds
    - **metrics**: Grouped statistics (keys depend on `group_by` and `metrics` params)
      - Format: `{metric}_by_{dimension}` (e.g., `clicks_by_browser`)
      - Each entry contains dimension value and metric count
    - **time_bucket_info**: Time bucketing details (only present if `group_by` includes `time`)
      - **strategy**: Bucketing strategy used (`hourly`, `daily`, `weekly`, `monthly`)
      - **timezone**: Timezone used for time buckets

    ## Example Use Cases

    ### 1. Get all stats for authenticated user (last 7 days)
    ```
    GET /api/v1/stats?scope=all
    Authorization: Bearer <jwt_token>
    ```

    ### 2. Anonymous access to public URL stats
    ```
    GET /api/v1/stats?scope=anon&short_code=mylink
    ```

    ### 3. Stats grouped by country and browser
    ```
    GET /api/v1/stats?scope=all&group_by=country,browser
    Authorization: Bearer <jwt_token>
    ```

    ### 4. Custom date range with timezone
    ```
    GET /api/v1/stats?scope=all&start_date=2024-01-01&end_date=2024-12-31&timezone=America/New_York
    Authorization: Bearer <jwt_token>
    ```

    ### 5. Filter by browser and country
    ```
    GET /api/v1/stats?scope=all&browser=Chrome,Firefox&country=US,CA
    Authorization: Bearer <jwt_token>
    ```

    ### 6. Multi-URL stats with filters
    ```
    GET /api/v1/stats?scope=all&filters={"short_code":["link1","link2"]}&group_by=short_code,country
    Authorization: Bearer <jwt_token>
    ```

    ## Error Responses
    - **400**: Invalid parameters, missing required fields, invalid date range
      - Invalid scope value
      - Missing `short_code` when `scope=anon`
      - Using `short_code` filter with `scope=anon` (security restriction)
      - Invalid `group_by` dimensions
      - Invalid `metrics` values
      - Invalid JSON in `filters` parameter
      - Invalid timezone (falls back to UTC with warning)
      - `start_date` after `end_date`
    - **401**: Authentication required, invalid token
      - Using `scope=all` without authentication
      - Accessing private stats without authentication
    - **403**: Insufficient permissions, private statistics, access denied
      - API key missing required `stats:read` scope
      - Accessing private stats when not the owner
    - **404**: URL/short_code not found, ownership validation failed
      - Invalid `short_code` in `scope=anon`
    - **429**: Rate limit exceeded
      - 60/min for authenticated users
      - 20/min for anonymous users
    - **500**: Database/server error

    ## Important Notes

    ### Security
    - **Private Stats**: URLs with `private_stats: true` require authentication and ownership
    - **Scope Isolation**: `scope=anon` prevents `short_code` filtering to prevent privacy bypass
    - **Rate Limits**: Higher limits for authenticated users (60/min vs 20/min)

    ### Time Handling
    - **Defaults**: 7-day window ending now if dates not specified
    - **Future Dates**: Automatically capped to current time
    - **Timezone Conversion**: All output timestamps converted to specified timezone
    - **Time Bucketing**: Automatic strategy selection based on date range
      - < 2 days: hourly buckets
      - 2-60 days: daily buckets
      - 60-365 days: weekly buckets
      - > 365 days: monthly buckets

    ### Filtering & Grouping
    - **Device Dimension**: Currently disabled (reliable detection not implemented)
    - **Multiple Dimensions**: Can group by multiple dimensions simultaneously
    - **Filter Combination**: Both JSON and individual filters can be used together
    - **Empty Results**: Returns zero counts, not errors, for no matching data

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
