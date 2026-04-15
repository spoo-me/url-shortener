"""
Service dependency providers.

Each function is a thin lookup that returns the singleton service instance
built during application startup in the lifespan (app.py).  No per-request
object construction — services are stateless and shared across requests.
"""

from __future__ import annotations

from bson import ObjectId
from fastapi import Request

from errors import NotFoundError
from repositories.app_grant_repository import AppGrantRepository
from repositories.user_repository import UserRepository
from schemas.models.user import UserDoc
from services.api_key_service import ApiKeyService
from services.auth.credentials import CredentialService
from services.auth.device import DeviceAuthService
from services.auth.password import PasswordService
from services.auth.verification import EmailVerificationService
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


def get_credential_service(request: Request) -> CredentialService:
    return request.app.state.credential_service


def get_verification_service(request: Request) -> EmailVerificationService:
    return request.app.state.verification_service


def get_password_service(request: Request) -> PasswordService:
    return request.app.state.password_service


def get_device_auth_service(request: Request) -> DeviceAuthService:
    return request.app.state.device_auth_service


def get_user_repo(request: Request) -> UserRepository:
    return request.app.state.user_repo


async def fetch_user_profile(user_repo: UserRepository, user_id: ObjectId) -> UserDoc:
    """Fetch a user by ID or raise NotFoundError.

    Thin helper used by route handlers that need a user profile
    without depending on a full auth service.
    """
    user = await user_repo.find_by_id(user_id)
    if not user:
        raise NotFoundError("user not found")
    return user


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
