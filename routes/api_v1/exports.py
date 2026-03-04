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
from middleware.rate_limiter import dynamic_limit, limiter
from schemas.dto.requests.stats import ExportQuery
from services.export.service import ExportService
from shared.datetime_utils import parse_datetime

router = APIRouter()

_STATS_SCOPES = {"stats:read", "urls:read", "admin:all"}

_export_limit, _export_key = dynamic_limit(
    "30 per minute; 1000 per day",
    "10 per minute; 200 per day",
)


@router.get("/export")
@limiter.limit(_export_limit, key_func=_export_key)
async def export_v1(
    request: Request,
    query: ExportQuery = Depends(),
    user: Optional[CurrentUser] = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    """Export URL click stats as a downloadable file.

    Scope (if API key): ``stats:read``, ``urls:read``, or ``admin:all``.
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
