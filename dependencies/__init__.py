"""
FastAPI dependency providers.

Re-exports all dependencies from sub-modules so that existing
``from dependencies import X`` imports continue to work unchanged.
"""

from dependencies.auth import (
    SHORTEN_SCOPES,
    STATS_SCOPES,
    URL_MANAGEMENT_SCOPES,
    URL_READ_SCOPES,
    AuthUser,
    CurrentUser,
    JwtUser,
    JwtVerifiedUser,
    OptionalUser,
    VerifiedUser,
    check_api_key_scope,
    get_current_user,
    optional_scopes,
    optional_scopes_verified,
    require_auth,
    require_jwt,
    require_jwt_verified,
    require_scopes,
    require_verified_email,
)
from dependencies.infra import (
    get_db,
    get_email_provider,
    get_geoip_service,
    get_redis,
    get_settings,
    get_url_cache,
)
from dependencies.services import (
    get_api_key_service,
    get_auth_service,
    get_click_service,
    get_contact_service,
    get_export_service,
    get_oauth_service,
    get_profile_picture_service,
    get_stats_service,
    get_url_service,
)

__all__ = [
    "SHORTEN_SCOPES",
    "STATS_SCOPES",
    "URL_MANAGEMENT_SCOPES",
    "URL_READ_SCOPES",
    # auth
    "AuthUser",
    "CurrentUser",
    "JwtUser",
    "JwtVerifiedUser",
    "OptionalUser",
    "VerifiedUser",
    "check_api_key_scope",
    # services
    "get_api_key_service",
    "get_auth_service",
    "get_click_service",
    "get_contact_service",
    "get_current_user",
    # infra
    "get_db",
    "get_email_provider",
    "get_export_service",
    "get_geoip_service",
    "get_oauth_service",
    "get_profile_picture_service",
    "get_redis",
    "get_settings",
    "get_stats_service",
    "get_url_cache",
    "get_url_service",
    "optional_scopes",
    "optional_scopes_verified",
    "require_auth",
    "require_jwt",
    "require_jwt_verified",
    "require_scopes",
    "require_verified_email",
]
