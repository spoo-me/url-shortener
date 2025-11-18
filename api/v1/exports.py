from flask import request, Response

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.auth_utils import resolve_owner_id_from_request
from builders import ExportBuilder

from . import api_v1


@api_v1.route("/export", methods=["GET"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="30 per minute; 1000 per day",
        anonymous="10 per minute; 200 per day",
    ),
    key_func=rate_limit_key_for_request,
)
def export_v1() -> tuple[Response, int]:
    """
    Export URL click statistics in various formats (CSV, XLSX, JSON, XML).

    This endpoint provides data export functionality with the same powerful filtering,
    grouping, and aggregation capabilities as the stats API, but returns formatted
    downloadable files instead of JSON responses.

    ## Authentication & Authorization
    - **JWT Token**: Use `Authorization: Bearer <jwt_token>` header
    - **API Key**: Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes**: `stats:read`, `urls:read`, or `admin:all`
    - **Rate Limits**: 30/min (auth), 10/min (anon)

    ## Query Parameters

    ### Required
    - **format** (string): Export file format
      - `"csv"` - Zipped CSV files (one per data category)
      - `"xlsx"` - Excel workbook with multiple sheets
      - `"json"` - JSON file with complete statistics
      - `"xml"` - XML file with complete statistics
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

    Returns a downloadable file in the requested format with appropriate MIME type:
    - **CSV**: `application/zip` (contains multiple CSV files)
    - **XLSX**: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
    - **JSON**: `application/json`
    - **XML**: `application/xml`

    ## Export File Structure

    ### CSV Export (Zipped)
    Contains multiple CSV files:
    - `summary.csv` - Overall statistics summary
    - `clicks_by_{dimension}.csv` - Click counts grouped by dimension
    - `unique_clicks_by_{dimension}.csv` - Unique click counts grouped by dimension

    ### XLSX Export
    Excel workbook with multiple sheets:
    - `Summary` - Overall statistics summary
    - `Clicks_by_{dimension}` - Click counts grouped by dimension
    - `Unique_Clicks_by_{dimension}` - Unique click counts grouped by dimension

    ### JSON Export
    Complete statistics in JSON format (same structure as stats API response)

    ### XML Export
    Complete statistics converted to XML format

    ## Example Use Cases

    ### 1. Export all user stats as Excel (last 7 days)
    ```
    GET /api/v1/export?format=xlsx&scope=all
    Authorization: Bearer <jwt_token>
    ```

    ### 2. Export public URL stats as CSV
    ```
    GET /api/v1/export?format=csv&scope=anon&short_code=mylink
    ```

    ### 3. Export filtered stats grouped by country
    ```
    GET /api/v1/export?format=xlsx&scope=all&group_by=country,browser&browser=Chrome,Firefox
    Authorization: Bearer <jwt_token>
    ```

    ### 4. Export custom date range as JSON
    ```
    GET /api/v1/export?format=json&scope=all&start_date=2024-01-01&end_date=2024-12-31
    Authorization: Bearer <jwt_token>
    ```

    ### 5. Export specific URLs with timezone
    ```
    GET /api/v1/export?format=xlsx&scope=all&filters={"short_code":["link1","link2"]}&timezone=America/New_York
    Authorization: Bearer <jwt_token>
    ```

    ## Error Responses
    - **400**: Invalid parameters
      - Missing required `format` parameter
      - Invalid format value (must be csv, xlsx, json, or xml)
      - Invalid scope value
      - Missing `short_code` when `scope=anon`
      - Using `short_code` filter with `scope=anon` (security restriction)
      - Invalid `group_by` dimensions
      - Invalid `metrics` values
      - Invalid JSON in `filters` parameter
      - Invalid timezone (falls back to UTC with warning)
      - `start_date` after `end_date`
    - **401**: Authentication required
      - Using `scope=all` without authentication
      - Accessing private stats without authentication
    - **403**: Insufficient permissions
      - API key missing required `stats:read` scope
      - Accessing private stats when not the owner
    - **404**: URL/short_code not found
      - Invalid `short_code` in `scope=anon`
    - **429**: Rate limit exceeded
      - 30/min for authenticated users
      - 10/min for anonymous users
    - **500**: Database/server error, export generation failed

    ## Important Notes

    ### Security
    - **Private Stats**: URLs with `private_stats: true` require authentication and ownership
    - **Scope Isolation**: `scope=anon` prevents `short_code` filtering to prevent privacy bypass
    - **Rate Limits**: Lower limits than stats API due to resource-intensive export generation

    ### File Sizes
    - Large exports may take time to generate
    - Consider using filters to reduce data volume for better performance
    - CSV format (zipped) is most efficient for large datasets

    ### Time Handling
    - **Defaults**: 7-day window ending now if dates not specified
    - **Future Dates**: Automatically capped to current time
    - **Timezone Conversion**: All output timestamps converted to specified timezone
    - **Time Bucketing**: Automatic strategy selection based on date range

    Returns:
        tuple[Response, int]: Downloadable file in requested format and HTTP status code
    """
    owner_id = resolve_owner_id_from_request()

    builder: ExportBuilder = (
        ExportBuilder(owner_id, request.args)
        .parse_format()
        .parse_stats()  # Reuses StatsQueryBuilder internally
        .build_export()
    )
    return builder.send()
