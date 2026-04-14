"""
Service and repository wiring — the composition root.

Called once during app startup to build all repositories, infrastructure,
and services as singletons on ``app.state``.  This keeps the lifespan
function in app.py focused on infrastructure lifecycle (connect/disconnect)
while this module handles the object graph.
"""

from __future__ import annotations

from fastapi import FastAPI

from config import AppSettings
from infrastructure.cache.url_cache import UrlCache
from infrastructure.captcha.hcaptcha import HCaptchaProvider
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


def wire_services(app: FastAPI, settings: AppSettings, redis_client) -> None:
    """Build all repositories and services, store on ``app.state``.

    Called once from the lifespan after infrastructure (db, redis, geoip,
    http_client, email_provider) is ready on ``app.state``.
    """
    db = app.state.db
    http_client = app.state.http_client

    # ── Repositories ─────────────────────────────────────────────────────
    url_repo = UrlRepository(db["urlsV2"])
    legacy_repo = LegacyUrlRepository(db["urls"])
    emoji_repo = EmojiUrlRepository(db["emojis"])
    click_repo = ClickRepository(db["clicks"])
    user_repo = UserRepository(db["users"])
    token_repo = TokenRepository(db["verification-tokens"])
    api_key_repo = ApiKeyRepository(db["api-keys"])
    blocked_url_repo = BlockedUrlRepository(db["blocked-urls"])
    app_grant_repo = AppGrantRepository(db["app-grants"])

    # ── Infrastructure ───────────────────────────────────────────────────
    url_cache = UrlCache(redis_client, ttl_seconds=settings.redis.redis_ttl_seconds)
    captcha = HCaptchaProvider(settings.hcaptcha_secret, http_client)
    contact_webhook = DiscordWebhookProvider(settings.contact_webhook, http_client)
    report_webhook = DiscordWebhookProvider(settings.url_report_webhook, http_client)

    # ── Services ─────────────────────────────────────────────────────────
    blocked_self_domains = [settings.app_url] if settings.app_url else []

    app.state.url_service = UrlService(
        url_repo,
        legacy_repo,
        emoji_repo,
        blocked_url_repo,
        url_cache,
        blocked_self_domains,
        blocked_url_regex_timeout=settings.blocked_url_regex_timeout,
        max_emoji_alias_length=settings.max_emoji_alias_length,
    )
    app.state.stats_service = StatsService(
        click_repo,
        url_repo,
        max_date_range_days=settings.max_date_range_days,
    )
    app.state.export_service = ExportService(
        app.state.stats_service,
        default_formatters(),
    )
    app.state.api_key_service = ApiKeyService(
        api_key_repo,
        max_active_keys=settings.max_active_api_keys,
    )
    app.state.auth_service = AuthService(
        user_repo,
        token_repo,
        app.state.email_provider,
        settings.jwt,
        account_password_min_length=settings.account_password_min_length,
        account_password_max_length=settings.account_password_max_length,
    )
    app.state.oauth_service = OAuthService(
        user_repo,
        app.state.auth_service,
        app.state.email_provider,
    )
    app.state.profile_picture_service = ProfilePictureService(user_repo)
    app.state.contact_service = ContactService(
        contact_webhook,
        report_webhook,
        captcha,
    )

    v2_handler = V2ClickHandler(click_repo, url_repo, app.state.geoip, url_cache)
    v1_handler = LegacyClickHandler(legacy_repo, emoji_repo, app.state.geoip)
    app.state.click_service = ClickService({"v2": v2_handler, "v1": v1_handler})

    app.state.app_grant_repo = app_grant_repo
