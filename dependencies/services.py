"""
Service dependency providers.

Each function is a thin lookup that returns the singleton service instance
built during application startup in the lifespan (app.py).  No per-request
object construction — services are stateless and shared across requests.
"""

from __future__ import annotations

from fastapi import Request

from repositories.app_grant_repository import AppGrantRepository
from services.api_key_service import ApiKeyService
from services.auth_service import AuthService
from services.click import ClickService
from services.contact_service import ContactService
from services.export.service import ExportService
from services.oauth_service import OAuthService
from services.profile_picture_service import ProfilePictureService
from services.stats_service import StatsService
from services.url_service import UrlService


def get_url_service(request: Request) -> UrlService:
    return request.app.state.url_service


def get_stats_service(request: Request) -> StatsService:
    return request.app.state.stats_service


def get_export_service(request: Request) -> ExportService:
    return request.app.state.export_service


def get_api_key_service(request: Request) -> ApiKeyService:
    return request.app.state.api_key_service


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_oauth_service(request: Request) -> OAuthService:
    return request.app.state.oauth_service


def get_profile_picture_service(request: Request) -> ProfilePictureService:
    return request.app.state.profile_picture_service


def get_contact_service(request: Request) -> ContactService:
    return request.app.state.contact_service


def get_click_service(request: Request) -> ClickService:
    return request.app.state.click_service


def get_app_grant_repo(request: Request) -> AppGrantRepository:
    return request.app.state.app_grant_repo
