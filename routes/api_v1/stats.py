"""
GET /api/v1/stats — URL click statistics.

Auth is optional for scope=anon (public stats); scope=all requires auth.
API key users require ``stats:read``, ``urls:read``, or ``admin:all``.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from dependencies import (
    CurrentUser,
    STATS_SCOPES,
    get_stats_service,
    optional_scopes,
)
from middleware.openapi import ERROR_RESPONSES, OPTIONAL_AUTH_SECURITY
from middleware.rate_limiter import Limits, dynamic_limit, limiter
from schemas.dto.requests.stats import StatsQuery
from schemas.dto.responses.stats import StatsResponse
from services.stats_service import StatsService
from shared.datetime_utils import parse_datetime

router = APIRouter(tags=["Statistics"])

_stats_limit, _stats_key = dynamic_limit(Limits.API_AUTHED, Limits.API_ANON)


@router.get(
    "/stats",
    responses=ERROR_RESPONSES,
    openapi_extra=OPTIONAL_AUTH_SECURITY,
    operation_id="getStats",
    summary="URL Statistics",
)
@limiter.limit(_stats_limit, key_func=_stats_key)
async def stats_v1(
    request: Request,
    query: Annotated[StatsQuery, Query()],
    user: Optional[CurrentUser] = Depends(optional_scopes(STATS_SCOPES)),
    stats_service: StatsService = Depends(get_stats_service),
) -> StatsResponse:
    """Get click statistics for URLs.

    Retrieve aggregated click analytics with flexible grouping, filtering,
    and time-range options.

    **Authentication**: Optional for `scope=anon` (public stats on a single URL);
    required for `scope=all` (all URLs owned by the user).

    **API Key Scope**: `stats:read`, `urls:read`, or `admin:all`

    **Rate Limits**:

    - Authenticated: 60/min, 5,000/day
    - Anonymous: 20/min, 1,000/day

    **Scopes**:

    - `scope=anon` + `short_code=<alias>` — public stats for one URL (if stats are not private)
    - `scope=all` — aggregate stats across all URLs owned by the authenticated user

    **Grouping Dimensions**: `time`, `browser`, `os`, `country`, `city`,
    `referrer`, `short_code`

    **Metrics**: `clicks`, `unique_clicks`

    **Filtering**: Filter by `browser`, `os`, `country`, `city`, `referrer`,
    or `short_code` using query params or a JSON `filters` object.
    """
    owner_id = str(user.user_id) if user is not None else None

    start_date = parse_datetime(query.start_date) if query.start_date else None
    end_date = parse_datetime(query.end_date) if query.end_date else None

    result = await stats_service.query(
        owner_id=owner_id,
        scope=query.scope,
        short_code=query.short_code,
        start_date=start_date,
        end_date=end_date,
        filters=query.parsed_filters,
        group_by=query.parsed_group_by,
        metrics=query.parsed_metrics,
        tz_name=query.timezone,
    )
    return StatsResponse.model_validate(result)
