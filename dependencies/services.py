"""
Service and repository dependency providers.

Each function assembles the repositories and infrastructure a service needs,
then returns a fully-wired service instance for the current request.
"""

from __future__ import annotations

from fastapi import Depends, Request

from config import AppSettings
from dependencies.infra import (
    get_db,
    get_email_provider,
    get_geoip_service,
    get_settings,
    get_url_cache,
)
from infrastructure.cache.url_cache import UrlCache
from infrastructure.captcha.hcaptcha import HCaptchaProvider
from infrastructure.geoip import GeoIPService
from infrastructure.webhook.discord import DiscordWebhookProvider
from repositories.api_key_repository import ApiKeyRepository
from repositories.app_grant_repository import AppGrantRepository
from repositories.blocked_url_repository import BlockedUrlRepository
from repositories.click_repository import ClickRepository
from repositories.legacy.emoji_url_repository import EmojiUrlRepository
from repositories.legacy.legacy_url_repository import LegacyUrlRepository
from repositories.token_repository import TokenRepository
from repositories.url_repository import UrlRepository
from repositories.user_repository import UserRepository
from services.api_key_service import ApiKeyService
from services.auth_service import AuthService
from services.click import ClickService, LegacyClickHandler, V2ClickHandler
from services.contact_service import ContactService
from services.export.formatters import default_formatters
from services.export.service import ExportService
from services.oauth_service import OAuthService
from services.profile_picture_service import ProfilePictureService
from services.stats_service import StatsService
from services.url_service import UrlService


async def get_app_grant_repo(db=Depends(get_db)) -> AppGrantRepository:
    """Return an AppGrantRepository for the current request."""
    return AppGrantRepository(db["app-grants"])


async def get_url_service(
    db=Depends(get_db),
    url_cache: UrlCache = Depends(get_url_cache),
    settings: AppSettings = Depends(get_settings),
) -> UrlService:
    url_repo = UrlRepository(db["urlsV2"])
    legacy_repo = LegacyUrlRepository(db["urls"])
    emoji_repo = EmojiUrlRepository(db["emojis"])
    blocked_url_repo = BlockedUrlRepository(db["blocked-urls"])
    blocked_self_domains = [settings.app_url] if settings.app_url else []
    return UrlService(
        url_repo,
        legacy_repo,
        emoji_repo,
        blocked_url_repo,
        url_cache,
        blocked_self_domains,
    )


async def get_stats_service(db=Depends(get_db)) -> StatsService:
    click_repo = ClickRepository(db["clicks"])
    url_repo = UrlRepository(db["urlsV2"])
    return StatsService(click_repo, url_repo)


async def get_export_service(
    stats: StatsService = Depends(get_stats_service),
) -> ExportService:
    return ExportService(stats, default_formatters())


async def get_api_key_service(db=Depends(get_db)) -> ApiKeyService:
    api_key_repo = ApiKeyRepository(db["api-keys"])
    return ApiKeyService(api_key_repo)


async def get_auth_service(
    db=Depends(get_db),
    settings: AppSettings = Depends(get_settings),
    email=Depends(get_email_provider),
) -> AuthService:
    """Build and return an AuthService for the current request."""
    user_repo = UserRepository(db["users"])
    token_repo = TokenRepository(db["verification-tokens"])
    return AuthService(user_repo, token_repo, email, settings.jwt)


async def get_oauth_service(
    db=Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    email=Depends(get_email_provider),
) -> OAuthService:
    """Build and return an OAuthService for the current request."""
    user_repo = UserRepository(db["users"])
    return OAuthService(user_repo, auth_service, email)


async def get_profile_picture_service(db=Depends(get_db)) -> ProfilePictureService:
    return ProfilePictureService(UserRepository(db["users"]))


async def get_contact_service(
    request: Request,
    settings: AppSettings = Depends(get_settings),
) -> ContactService:
    http_client = request.app.state.http_client
    captcha = HCaptchaProvider(settings.hcaptcha_secret, http_client)
    contact_webhook = DiscordWebhookProvider(settings.contact_webhook, http_client)
    report_webhook = DiscordWebhookProvider(settings.url_report_webhook, http_client)
    return ContactService(contact_webhook, report_webhook, captcha)


async def get_click_service(
    db=Depends(get_db),
    url_cache: UrlCache = Depends(get_url_cache),
    geoip: GeoIPService = Depends(get_geoip_service),
) -> ClickService:
    """Build and return a ClickService with V2 and legacy handlers."""
    url_repo = UrlRepository(db["urlsV2"])
    legacy_repo = LegacyUrlRepository(db["urls"])
    emoji_repo = EmojiUrlRepository(db["emojis"])
    click_repo = ClickRepository(db["clicks"])
    v2_handler = V2ClickHandler(click_repo, url_repo, geoip, url_cache)
    v1_handler = LegacyClickHandler(legacy_repo, emoji_repo, geoip)
    return ClickService({"v2": v2_handler, "v1": v1_handler})
