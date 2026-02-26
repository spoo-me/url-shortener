"""OAuth provider strategies and Authlib client initialisation.

Relocated from utils/oauth_providers.py and utils/oauth_utils.py.
Strategy ABC + registry are unchanged. Authlib init adapted for
FastAPI/Starlette (no Flask app; clients stored on app.state).

Functions that touch the database (find_user_by_provider, create_oauth_user,
link_provider_to_user, etc.) will move to the service layer in Phase 7.
For now they remain here to keep the migration non-breaking.
"""

import os
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from authlib.integrations.starlette_client import OAuth

from shared.logging import get_logger

log = get_logger(__name__)


# ── Provider strategies ───────────────────────────────────────────────────────


class OAuthProviderStrategy(ABC):
    """Encapsulates everything that differs between OAuth providers."""

    @property
    @abstractmethod
    def key(self) -> str: ...

    @abstractmethod
    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]: ...


class GoogleStrategy(OAuthProviderStrategy):
    key = "google"

    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        userinfo = token.get("userinfo")
        if userinfo is None:
            resp = client.get("userinfo", token=token)
            resp.raise_for_status()
            userinfo = resp.json()
        return extract_user_info_from_google(userinfo)


class GitHubStrategy(OAuthProviderStrategy):
    key = "github"

    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        user_response = client.get("user", token=token)
        user_response.raise_for_status()
        user = user_response.json()
        emails_response = client.get("user/emails", token=token)
        emails = emails_response.json() if emails_response.status_code == 200 else []
        if not isinstance(emails, list):
            emails = []
        return extract_user_info_from_github(user, emails)


class DiscordStrategy(OAuthProviderStrategy):
    key = "discord"

    def fetch_user_info(self, client: Any, token: Any) -> dict[str, Any]:
        resp = client.get("users/@me", token=token)
        resp.raise_for_status()
        return extract_user_info_from_discord(resp.json())


PROVIDER_STRATEGIES: dict[str, OAuthProviderStrategy] = {
    s.key: s() for s in [GoogleStrategy, GitHubStrategy, DiscordStrategy]
}


# ── Authlib init ─────────────────────────────────────────────────────────────


def init_oauth(settings: Any) -> Tuple[Optional[OAuth], Dict[str, Any]]:
    """Initialise Authlib OAuth clients for FastAPI/Starlette.

    Accepts an OAuthProviderSettings instance (from config.py).
    Returns (oauth, providers_dict) — store both on app.state in create_app().
    Returns (None, {}) if no providers are configured.
    """
    oauth = OAuth()
    providers: Dict[str, Any] = {}

    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        try:
            google = oauth.register(
                name="google",
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={
                    "scope": "openid email profile",
                    "prompt": "select_account",
                },
            )
            providers["google"] = google
            log.info("oauth_provider_initialized", provider="google")
        except Exception as e:
            log.error("oauth_provider_init_failed", provider="google", error=str(e))

    if settings.github_oauth_client_id and settings.github_oauth_client_secret:
        try:
            github = oauth.register(
                name="github",
                client_id=settings.github_oauth_client_id,
                client_secret=settings.github_oauth_client_secret,
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com/",
                client_kwargs={"scope": "user:email"},
            )
            providers["github"] = github
            log.info("oauth_provider_initialized", provider="github")
        except Exception as e:
            log.error("oauth_provider_init_failed", provider="github", error=str(e))

    if settings.discord_oauth_client_id and settings.discord_oauth_client_secret:
        try:
            discord = oauth.register(
                name="discord",
                client_id=settings.discord_oauth_client_id,
                client_secret=settings.discord_oauth_client_secret,
                access_token_url="https://discord.com/api/oauth2/token",
                authorize_url="https://discord.com/api/oauth2/authorize",
                api_base_url="https://discord.com/api/",
                client_kwargs={"scope": "identify email"},
            )
            providers["discord"] = discord
            log.info("oauth_provider_initialized", provider="discord")
        except Exception as e:
            log.error("oauth_provider_init_failed", provider="discord", error=str(e))

    if not providers:
        log.warning("oauth_no_providers_configured")
        return None, {}

    return oauth, providers


# ── State utilities ───────────────────────────────────────────────────────────


def generate_oauth_state(
    provider: str, action: str = "login", user_id: Optional[str] = None
) -> str:
    """Generate a URL-safe state string for CSRF protection."""
    parts = [
        f"provider={provider}",
        f"action={action}",
        f"nonce={secrets.token_urlsafe(32)}",
        f"timestamp={datetime.now(timezone.utc).isoformat()}",
    ]
    if user_id:
        parts.append(f"user_id={user_id}")
    return "&".join(parts)


def verify_oauth_state(
    state: str, expected_provider: str
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Verify and decode an OAuth state string.

    Returns (is_valid, state_data, failure_reason).
    failure_reason is None on success; one of "provider_mismatch",
    "missing_timestamp", "expired", or "parse_error" on failure.
    """
    try:
        state_data: Dict[str, Any] = {}
        for part in state.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                state_data[key] = value

        if state_data.get("provider") != expected_provider:
            return False, {}, "provider_mismatch"

        timestamp_str = state_data.get("timestamp")
        if not timestamp_str:
            return False, {}, "missing_timestamp"

        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        if age > 600:
            return False, {}, "expired"

        return True, state_data, None
    except Exception:
        return False, {}, "parse_error"


def get_oauth_redirect_url(provider: str, settings: Any) -> str:
    """Return the OAuth redirect URI from settings, or build a default.

    Checks {PROVIDER}_OAUTH_REDIRECT_URI setting first, then falls back to
    constructing a standard callback URL. In the new FastAPI app, call this
    from the route handler where the base URL is known.
    """
    env_redirect = getattr(settings, f"{provider}_oauth_redirect_uri", "")
    if env_redirect:
        return env_redirect
    # Fallback: callers must supply base_url explicitly in the FastAPI route.
    return ""


# ── User-info extractors ──────────────────────────────────────────────────────


def extract_user_info_from_google(userinfo: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider_user_id": userinfo.get("sub", ""),
        "email": userinfo.get("email", "").lower().strip(),
        "email_verified": userinfo.get("email_verified", False),
        "name": userinfo.get("name", ""),
        "picture": userinfo.get("picture", ""),
        "given_name": userinfo.get("given_name", ""),
        "family_name": userinfo.get("family_name", ""),
    }


def extract_user_info_from_github(
    userinfo: Dict[str, Any], email_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    primary_email = ""
    email_verified = False
    for entry in email_data:
        if entry.get("primary", False):
            primary_email = entry.get("email", "").lower().strip()
            email_verified = entry.get("verified", False)
            break
    if not primary_email and email_data:
        primary_email = email_data[0].get("email", "").lower().strip()
        email_verified = email_data[0].get("verified", False)

    name = userinfo.get("name", "") or userinfo.get("login", "")
    return {
        "provider_user_id": str(userinfo.get("id", "")),
        "email": primary_email,
        "email_verified": email_verified,
        "name": name,
        "picture": userinfo.get("avatar_url", ""),
        "given_name": name.split(" ")[0] if name else "",
        "family_name": " ".join(name.split(" ")[1:]) if name and " " in name else "",
    }


def extract_user_info_from_discord(userinfo: Dict[str, Any]) -> Dict[str, Any]:
    email = userinfo.get("email", "").lower().strip()
    email_verified = userinfo.get("verified", False)
    name = (
        userinfo.get("global_name")
        or userinfo.get("display_name")
        or userinfo.get("username", "")
    )
    avatar_hash = userinfo.get("avatar")
    user_id = userinfo.get("id", "")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
        if avatar_hash and user_id
        else ""
    )
    return {
        "provider_user_id": str(userinfo.get("id", "")),
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": avatar_url,
        "given_name": name.split(" ")[0] if name and " " in name else name,
        "family_name": " ".join(name.split(" ")[1:]) if name and " " in name else "",
    }


def can_auto_link_accounts(
    existing_user: Dict[str, Any], provider_info: Dict[str, Any], provider: str
) -> bool:
    """True only if provider email is verified, matches user email, and isn't already linked."""
    if not provider_info.get("email_verified", False):
        return False
    if existing_user.get("email", "").lower() != provider_info.get("email", "").lower():
        return False
    for entry in existing_user.get("auth_providers", []):
        if entry.get("provider") == provider:
            return False
    return True
