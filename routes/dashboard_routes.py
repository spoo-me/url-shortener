"""
Dashboard routes — template-rendering pages and profile picture API.

GET  /dashboard             → redirect to /dashboard/links
GET  /dashboard/links       → links management page
GET  /dashboard/keys        → API keys page
GET  /dashboard/statistics  → statistics page
GET  /dashboard/settings    → settings page
GET  /dashboard/billing     → billing page
GET  /dashboard/apps          → connected apps + ecosystem
GET  /dashboard/profile-pictures  → available pictures (JSON)
POST /dashboard/profile-pictures  → set profile picture (JSON)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from dependencies import (
    AuthUser,
    CurrentUser,
    OptionalUser,
    get_app_grant_repo,
    get_profile_picture_service,
)
from errors import NotFoundError
from middleware.rate_limiter import Limits, limiter
from repositories.app_grant_repository import AppGrantRepository
from schemas.models.app import AppEntry, AppStatus
from services.profile_picture_service import AvailablePicture, ProfilePictureService
from shared.logging import get_logger
from shared.templates import templates

log = get_logger(__name__)

router = APIRouter(prefix="/dashboard", include_in_schema=False)


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
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_root(
    request: Request,
    user: OptionalUser,
) -> Response:
    if user is None:
        return _unauth_redirect()
    return RedirectResponse("/dashboard/links", status_code=302)


@router.get("/links")
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_links(
    request: Request,
    user: OptionalUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/links.html", request, user, svc)


@router.get("/keys")
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_keys(
    request: Request,
    user: OptionalUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/keys.html", request, user, svc)


@router.get("/statistics")
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_statistics(
    request: Request,
    user: OptionalUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/statistics.html", request, user, svc)


@router.get("/settings")
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_settings(
    request: Request,
    user: OptionalUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/settings.html", request, user, svc)


@router.get("/billing")
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_billing(
    request: Request,
    user: OptionalUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    return await _render_dashboard_page("dashboard/billing.html", request, user, svc)


@router.get("/apps")
@limiter.limit(Limits.DASHBOARD_READ)
async def dashboard_apps(
    request: Request,
    user: OptionalUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
    grant_repo: AppGrantRepository = Depends(get_app_grant_repo),
) -> Response:
    if user is None:
        return _unauth_redirect()
    profile = await svc.get_dashboard_profile(user.user_id)
    grants = await grant_repo.find_active_for_user(user.user_id)
    app_registry: dict[str, AppEntry] = request.app.state.app_registry
    grant_map = {g.app_id: g for g in grants}

    connected: list[dict] = []
    available: list[dict] = []
    coming_soon: list[dict] = []

    for app_id, app in app_registry.items():
        entry = {"app_id": app_id, **app.model_dump()}
        if app.status == AppStatus.COMING_SOON:
            coming_soon.append(entry)
        elif app_id in grant_map:
            entry["grant"] = grant_map[app_id]
            connected.append(entry)
        else:
            available.append(entry)

    return templates.TemplateResponse(
        request,
        "dashboard/apps.html",
        {
            "host_url": str(request.base_url),
            "user": profile,
            "connected": connected,
            "available": available,
            "coming_soon": coming_soon,
        },
    )


# ── Profile pictures (JSON API) ─────────────────────────────────────────────


class SetProfilePictureRequest(BaseModel):
    picture_id: str = Field(min_length=1, max_length=200)


class AvailablePicturesResponse(BaseModel):
    pictures: list[AvailablePicture]


class ProfilePictureMessageResponse(BaseModel):
    message: str


@router.get("/profile-pictures")
@limiter.limit(Limits.DASHBOARD_READ)
async def get_profile_pictures(
    request: Request,
    user: AuthUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> AvailablePicturesResponse:
    pictures = await svc.get_available_pictures(user.user_id)
    return AvailablePicturesResponse(pictures=pictures)


@router.post("/profile-pictures")
@limiter.limit(Limits.PROFILE_PICTURE_SET)
async def set_profile_picture(
    request: Request,
    body: SetProfilePictureRequest,
    user: AuthUser,
    svc: ProfilePictureService = Depends(get_profile_picture_service),
) -> Response:
    try:
        await svc.set_picture(user.user_id, body.picture_id)
    except NotFoundError as exc:
        log.warning(
            "profile_picture_not_found", user_id=str(user.user_id), error=str(exc)
        )
        return JSONResponse({"error": "Profile picture not found"}, status_code=404)

    return ProfilePictureMessageResponse(message="Profile picture updated successfully")
