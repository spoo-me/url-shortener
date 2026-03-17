"""
FastAPI dependency providers.

Re-exports all dependencies from sub-modules so that existing
``from dependencies import X`` imports continue to work unchanged.
"""

from dependencies.auth import (
    CurrentUser,
    check_api_key_scope,
    get_current_user,
    require_auth,
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
    # auth
    "CurrentUser",
    "check_api_key_scope",
    "get_current_user",
    "require_auth",
    "require_verified_email",
    # infra
    "get_db",
    "get_email_provider",
    "get_geoip_service",
    "get_redis",
    "get_settings",
    "get_url_cache",
    # services
    "get_api_key_service",
    "get_auth_service",
    "get_click_service",
    "get_contact_service",
    "get_export_service",
    "get_oauth_service",
    "get_profile_picture_service",
    "get_stats_service",
    "get_url_service",
]
