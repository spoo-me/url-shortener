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
    """
    List all shortened URLs owned by the authenticated user with pagination, filtering, and sorting.

    This endpoint provides a comprehensive view of all URLs created by the authenticated user,
    with support for flexible querying, pagination, multi-field filtering, and custom sorting.

    ## Authentication & Authorization
    - **JWT Token** (required): Use `Authorization: Bearer <jwt_token>` header
    - **API Key** (required): Use `Authorization: Bearer spoo_<api_key>` header
    - **Required Scopes**: `urls:manage`, `urls:read`, or `admin:all`
    - **Rate Limits**: 60/min & 5000/day (auth), Anonymous: Disabled

    ## Query Parameters

    ### Pagination
    - **page** (integer): Page number (default: 1, min: 1)
    - **pageSize** (integer): Items per page (default: 20, min: 1, max: 100)

    ### Sorting
    - **sortBy** (string): Field to sort by (default: "created_at")
      - Options: "created_at", "last_click", "total_clicks"
    - **sortOrder** (string): Sort direction (default: "descending")
      - Options: "ascending"/"asc"/"1", "descending"/"desc"/"-1"

    ### Filtering
    You can provide filters in two ways:

    #### Method 1: JSON filter object (recommended for complex filters)
    - **filter** (JSON string): Complex filter object
      ```json
      {
        "status": "ACTIVE",
        "createdAfter": "2024-01-01T00:00:00Z",
        "createdBefore": "2024-12-31T23:59:59Z",
        "passwordSet": true,
        "maxClicksSet": false,
        "search": "example"
      }
      ```

    #### Method 2: Individual query parameters
    All filter fields can also be passed as individual query parameters:
    - **status** (string): Filter by status ("ACTIVE" or "INACTIVE")
    - **createdAfter** (string): ISO 8601 datetime or Unix timestamp
    - **createdBefore** (string): ISO 8601 datetime or Unix timestamp
    - **passwordSet** (boolean): Filter by password protection (true/false)
    - **maxClicksSet** (boolean): Filter by click limit presence (true/false)
    - **search** (string): Search in alias or long_url (case-insensitive)

    ## Example Requests

    ### Basic pagination
    ```
    GET /api/v1/urls?page=1&pageSize=20
    ```

    ### With sorting
    ```
    GET /api/v1/urls?sortBy=total_clicks&sortOrder=descending
    ```

    ### With JSON filter
    ```
    GET /api/v1/urls?filter={"status":"ACTIVE","passwordSet":true}
    ```

    ### With search
    ```
    GET /api/v1/urls?filter={"search":"example"}
    ```

    ### Combined example
    ```
    GET /api/v1/urls?page=2&pageSize=50&sortBy=last_click&sortOrder=desc&filter={"status":"ACTIVE","createdAfter":"2024-01-01"}
    ```

    ## Response Format
    ```json
    {
      "items": [
        {
          "id": "507f1f77bcf86cd799439011",
          "alias": "mylink",
          "long_url": "https://example.com/destination",
          "status": "ACTIVE",
          "created_at": "2024-01-01T12:00:00Z",
          "expire_after": 1735689600,
          "max_clicks": 100,
          "private_stats": false,
          "block_bots": false,
          "password_set": true,
          "total_clicks": 42,
          "last_click": "2024-01-07T15:30:00Z"
        }
      ],
      "page": 1,
      "pageSize": 20,
      "total": 150,
      "hasNext": true,
      "sortBy": "created_at",
      "sortOrder": "descending"
    }
    ```

    ## Response Fields
    - **items**: Array of URL objects
    - **page**: Current page number
    - **pageSize**: Items per page
    - **total**: Total number of URLs matching filters
    - **hasNext**: Boolean indicating if more pages exist
    - **sortBy**: Field used for sorting
    - **sortOrder**: Sort direction applied

    ## Error Responses
    - **400**: Invalid pagination parameters, invalid filter JSON, invalid sort field
    - **401**: Authentication required, invalid token
    - **403**: Insufficient permissions (missing required scope)
    - **429**: Rate limit exceeded
    - **500**: Database/server error

    Returns:
        tuple[Response, int]: JSON response with paginated URL list and HTTP status code
    """
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
