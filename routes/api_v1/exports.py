"""
GET /api/v1/export — export URL stats as CSV, XLSX, JSON, or XML.

Auth is optional for scope=anon (public stats); scope=all requires auth.
API key users require ``stats:read``, ``urls:read``, or ``admin:all``.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from dependencies import (
    CurrentUser,
    STATS_SCOPES,
    get_export_service,
    optional_scopes,
)
from middleware.openapi import EXPORT_RESPONSES, OPTIONAL_AUTH_SECURITY
from middleware.rate_limiter import Limits, dynamic_limit, limiter
from schemas.dto.requests.stats import ExportQuery
from services.export.service import ExportService
from shared.datetime_utils import parse_datetime

router = APIRouter(tags=["Statistics"])

_export_limit, _export_key = dynamic_limit(
    Limits.API_EXPORT_AUTHED, Limits.API_EXPORT_ANON
)


@router.get(
    "/export",
    responses={
        **EXPORT_RESPONSES,
        200: {
            "description": "Export file download",
            "content": {
                "application/json": {
                    "schema": {"type": "string", "format": "binary"},
                },
                "application/xml": {
                    "schema": {"type": "string", "format": "binary"},
                },
                "application/zip": {
                    "schema": {"type": "string", "format": "binary"},
                    "x-description": "CSV export — ZIP archive containing summary.csv plus one file per dimension",
                },
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"},
                    "x-description": "XLSX export — Excel workbook with multiple sheets",
                },
            },
        },
    },
    openapi_extra=OPTIONAL_AUTH_SECURITY,
    operation_id="exportStats",
    summary="Export Statistics",
)
@limiter.limit(_export_limit, key_func=_export_key)
async def export_v1(
    request: Request,
    query: Annotated[ExportQuery, Query()],
    user: Optional[CurrentUser] = Depends(optional_scopes(STATS_SCOPES)),
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
