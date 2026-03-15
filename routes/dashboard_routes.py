"""
Dashboard routes — template-rendering pages and profile picture API.

GET  /dashboard             → redirect to /dashboard/links
GET  /dashboard/links       → links management page
GET  /dashboard/keys        → API keys page
GET  /dashboard/statistics  → statistics page
GET  /dashboard/settings    → settings page
GET  /dashboard/billing     → billing page
GET  /dashboard/profile-pictures  → available pictures (JSON)
POST /dashboard/profile-pictures  → set profile picture (JSON)
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dependencies import (
    CurrentUser,
    get_current_user,
    get_profile_picture_service,
    require_auth,
)
from errors import NotFoundError
from middleware.rate_limiter import limiter
from services.profile_picture_service import ProfilePictureService
from shared.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/dashboard", include_in_schema=False)

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _unauth_redirect() -> Response:
    return RedirectResponse("/?login=true", status_code=302)


async def _render_dashboard_page(
    template_name: str,
    request: Request,
    user: CurrentUser | None,
    svc: ProfilePictureService,
) -> Response:
    """Shared logic for all dashboard page routes — auth check + profile fetch + render."""
    if user is None:
        return _unauth_redirect()
    profile = await svc.get_dashboard_profile(user.user_id)
    return templates.TemplateResponse(
        request,
        template_name,
        {"host_url": str(request.base_url), "user": profile},
    )


# ── Page routes ──────────────────────────────────────────────────────────────


@router.get("")
@router.get("/")
@limiter.limit("30 per minute")
async def dashboard_root(
    request: Request,
    user: CurrentUser | None = Depends(get_current_user),
) -> Response:
    if user is None:
        return _unauth_redirect()
    return RedirectResponse("/dashboard/links", status_code=302)


@router.get("/links")
@limiter.limit("30 per minute")
async def dashboard_links(
    request: Request,
    user: CurrentUser | None = Depends(get_current_user),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/links.html", request, user, svc)


@router.get("/keys")
@limiter.limit("30 per minute")
async def dashboard_keys(
    request: Request,
    user: CurrentUser | None = Depends(get_current_user),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/keys.html", request, user, svc)


@router.get("/statistics")
@limiter.limit("30 per minute")
async def dashboard_statistics(
    request: Request,
    user: CurrentUser | None = Depends(get_current_user),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/statistics.html", request, user, svc)


@router.get("/settings")
@limiter.limit("30 per minute")
async def dashboard_settings(
    request: Request,
    user: CurrentUser | None = Depends(get_current_user),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/settings.html", request, user, svc)


@router.get("/billing")
@limiter.limit("30 per minute")
async def dashboard_billing(
    request: Request,
    user: CurrentUser | None = Depends(get_current_user),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/billing.html", request, user, svc)


# ── Profile pictures (JSON API) ─────────────────────────────────────────────


class SetProfilePictureRequest(BaseModel):
    picture_id: str


@router.get("/profile-pictures")
@limiter.limit("30 per minute")
async def get_profile_pictures(
    request: Request,
    user: CurrentUser = Depends(require_auth),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    pictures = await svc.get_available_pictures(user.user_id)
    return JSONResponse({"pictures": pictures})


@router.post("/profile-pictures")
@limiter.limit("10 per minute")
async def set_profile_picture(
    request: Request,
    body: SetProfilePictureRequest,
    user: CurrentUser = Depends(require_auth),
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    try:
        await svc.set_picture(user.user_id, body.picture_id)
    except NotFoundError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

    return JSONResponse({"message": "Profile picture updated successfully"})
