"""
GET /api/v1/export — export URL stats as CSV, XLSX, JSON, or XML.

Auth is optional for scope=anon (public stats); scope=all requires auth.
API key users require ``stats:read``, ``urls:read``, or ``admin:all``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from dependencies import (
    CurrentUser,
    check_api_key_scope,
    get_current_user,
    get_export_service,
)
from middleware.openapi import EXPORT_RESPONSES, OPTIONAL_AUTH_SECURITY
from middleware.rate_limiter import dynamic_limit, limiter
from schemas.dto.requests.stats import ExportQuery
from services.export.service import ExportService
from shared.datetime_utils import parse_datetime

router = APIRouter(tags=["Statistics"])

_STATS_SCOPES = {"stats:read", "urls:read", "admin:all"}

_export_limit, _export_key = dynamic_limit(
    "30 per minute; 1000 per day",
    "10 per minute; 200 per day",
)


@router.get(
    "/export",
    responses=EXPORT_RESPONSES,
    openapi_extra=OPTIONAL_AUTH_SECURITY,
    operation_id="exportStats",
    summary="Export Statistics",
)
@limiter.limit(_export_limit, key_func=_export_key)
async def export_v1(
    request: Request,
    query: ExportQuery = Depends(),
    user: Optional[CurrentUser] = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    """Export URL click statistics as a downloadable file.

    Generate a file export of click analytics data in the specified format.
    The response is a binary download with appropriate `Content-Disposition` header.

    **Authentication**: Optional for `scope=anon` (public stats on a single URL);
    required for `scope=all`.

    **API Key Scope**: `stats:read`, `urls:read`, or `admin:all`

    **Rate Limits**:
    - Authenticated: 30/min, 1,000/day
    - Anonymous: 10/min, 200/day

    **Export Formats**:
    - `json` — single JSON file
    - `xml` — single XML file
    - `xlsx` — Excel spreadsheet with multiple sheets
    - `csv` — **ZIP archive** containing `summary.csv` plus one CSV file per metrics dimension

    **Note**: Export generation is resource-intensive. Lower rate limits apply
    compared to other endpoints.
    """
    check_api_key_scope(user, _STATS_SCOPES)

    owner_id = str(user.user_id) if user is not None else None

    start_date = parse_datetime(query.start_date) if query.start_date else None
    end_date = parse_datetime(query.end_date) if query.end_date else None

    data, mimetype, filename = await export_service.export(
        fmt=query.format,
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

    return Response(
        content=data,
        media_type=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
