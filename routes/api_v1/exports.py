"""
GET /api/v1/export — export URL stats as CSV, XLSX, JSON, or XML.

Auth is optional for scope=anon (public stats); scope=all requires auth.
API key users require ``stats:read``, ``urls:read``, or ``admin:all``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from dependencies import (
    STATS_SCOPES,
    CurrentUser,
    ExportSvc,
    optional_scopes,
)
from middleware.openapi import EXPORT_RESPONSES, OPTIONAL_AUTH_SECURITY
from middleware.rate_limiter import Limits, dynamic_limit, limiter
from schemas.dto.requests.stats import ExportQuery

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
    export_service: ExportSvc,
    user: CurrentUser | None = Depends(optional_scopes(STATS_SCOPES)),  # noqa: B008
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
    result = await export_service.export(query, owner_id)
    return Response(
        content=result.content,
        media_type=result.mimetype,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
