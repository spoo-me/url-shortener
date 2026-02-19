import os
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any, List

from authlib.integrations.flask_client import OAuth
from flask import url_for

from utils.mongo_utils import users_collection
from utils.url_utils import get_client_ip
from utils.logger import get_logger

log = get_logger(__name__)


class OAuthProviders:
    GOOGLE = "google"
    GITHUB = "github"
    DISCORD = "discord"
    # Future providers can be added here


def init_oauth(app):
    """Initialize OAuth with Flask app"""
    # Check if OAuth credentials are configured
    google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    github_client_id = os.getenv("GITHUB_OAUTH_CLIENT_ID")
    github_client_secret = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
    discord_client_id = os.getenv("DISCORD_OAUTH_CLIENT_ID")
    discord_client_secret = os.getenv("DISCORD_OAUTH_CLIENT_SECRET")

    oauth = OAuth(app)
    providers = {}

    # Google OAuth configuration
    if google_client_id and google_client_secret:
        try:
            google = oauth.register(
                name="google",
                client_id=google_client_id,
                client_secret=google_client_secret,
                server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                client_kwargs={
                    "scope": "openid email profile",
                    "prompt": "select_account",  # Always show account selector
                },
            )
            providers["google"] = google
            log.info("oauth_provider_initialized", provider="google")
        except Exception as e:
            log.error(
                "oauth_provider_init_failed",
                provider="google",
                error=str(e),
                error_type=type(e).__name__,
            )

    # GitHub OAuth configuration
    if github_client_id and github_client_secret:
        try:
            github = oauth.register(
                name="github",
                client_id=github_client_id,
                client_secret=github_client_secret,
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com/",
                client_kwargs={
                    "scope": "user:email",
                },
            )
            providers["github"] = github
            log.info("oauth_provider_initialized", provider="github")
        except Exception as e:
            log.error(
                "oauth_provider_init_failed",
                provider="github",
                error=str(e),
                error_type=type(e).__name__,
            )

    # Discord OAuth configuration
    if discord_client_id and discord_client_secret:
        try:
            discord = oauth.register(
                name="discord",
                client_id=discord_client_id,
                client_secret=discord_client_secret,
                access_token_url="https://discord.com/api/oauth2/token",
                authorize_url="https://discord.com/api/oauth2/authorize",
                api_base_url="https://discord.com/api/",
                client_kwargs={
                    "scope": "identify email",
                },
            )
            providers["discord"] = discord
            log.info("oauth_provider_initialized", provider="discord")
        except Exception as e:
            log.error(
                "oauth_provider_init_failed",
                provider="discord",
                error=str(e),
                error_type=type(e).__name__,
            )

    if not providers:
        log.warning("oauth_no_providers_configured")
        return None, {}

    return oauth, providers


def generate_oauth_state(
    provider: str, action: str = "login", user_id: Optional[str] = None
) -> str:
    """Generate a secure state parameter for OAuth flows

    Args:
        provider: OAuth provider name (e.g., 'google')
        action: Action being performed ('login' or 'link')
        user_id: Optional user ID for account linking (must be inside signed state)

    Returns:
        Encoded state string
    """
    state_data = {
        "provider": provider,
        "action": action,
        "nonce": secrets.token_urlsafe(32),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # CRITICAL: Include user_id INSIDE the state before signing to prevent tampering
    if user_id:
        state_data["user_id"] = user_id

    # For simplicity, we'll use a URL-safe encoding
    # TODO: In production, you should sign this with a secret key for better security
    # Consider using JWT or HMAC signing for the state parameter
    state_parts = [
        f"provider={state_data['provider']}",
        f"action={state_data['action']}",
        f"nonce={state_data['nonce']}",
        f"timestamp={state_data['timestamp']}",
    ]

    # Include user_id in the state parts if present
    if user_id:
        state_parts.append(f"user_id={user_id}")

    return "&".join(state_parts)


def verify_oauth_state(
    state: str, expected_provider: str
) -> Tuple[bool, Dict[str, Any]]:
    """Verify and decode OAuth state parameter

    Args:
        state: State parameter from OAuth callback
        expected_provider: Expected provider name

    Returns:
        Tuple of (is_valid, state_data)
    """
    try:
        # Parse state
        state_data = {}
        for part in state.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                state_data[key] = value

        # Basic validation
        if state_data.get("provider") != expected_provider:
            return False, {}

        # Check timestamp (state should not be older than 10 minutes)
        timestamp_str = state_data.get("timestamp")
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - timestamp).total_seconds()
            if age > 600:  # 10 minutes
                return False, {}

        return True, state_data
    except Exception:
        return False, {}


def extract_user_info_from_google(userinfo: Dict[str, Any]) -> Dict[str, Any]:
    """Extract standardized user information from Google OAuth response

    Args:
        userinfo: User info from Google OAuth

    Returns:
        Standardized user info dict
    """
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
    """Extract standardized user information from GitHub OAuth response

    Args:
        userinfo: User info from GitHub OAuth
        email_data: Email data from GitHub API

    Returns:
        Standardized user info dict
    """
    # Find primary verified email
    primary_email = None
    email_verified = False

    for email in email_data:
        if email.get("primary", False):
            primary_email = email.get("email", "").lower().strip()
            email_verified = email.get("verified", False)
            break

    # Fallback to first email if no primary found
    if not primary_email and email_data:
        primary_email = email_data[0].get("email", "").lower().strip()
        email_verified = email_data[0].get("verified", False)

    return {
        "provider_user_id": str(userinfo.get("id", "")),
        "email": primary_email or "",
        "email_verified": email_verified,
        "name": userinfo.get("name", "") or userinfo.get("login", ""),
        "picture": userinfo.get("avatar_url", ""),
        "given_name": userinfo.get("name", "").split(" ")[0]
        if userinfo.get("name")
        else "",
        "family_name": " ".join(userinfo.get("name", "").split(" ")[1:])
        if userinfo.get("name") and " " in userinfo.get("name", "")
        else "",
    }


def extract_user_info_from_discord(userinfo: Dict[str, Any]) -> Dict[str, Any]:
    """Extract standardized user information from Discord OAuth response

    Args:
        userinfo: User info from Discord OAuth

    Returns:
        Standardized user info dict
    """
    # Discord provides email directly in the user object when email scope is granted
    email = userinfo.get("email", "").lower().strip()
    email_verified = userinfo.get("verified", False)

    # Build full name from global_name (display name) or username
    # Note: Discord removed discriminators, so we use global_name or username
    name = (
        userinfo.get("global_name")
        or userinfo.get("display_name")
        or userinfo.get("username", "")
    )

    # Build avatar URL
    avatar_hash = userinfo.get("avatar")
    user_id = userinfo.get("id", "")
    avatar_url = ""
    if avatar_hash and user_id:
        # Discord CDN avatar URL format
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"

    return {
        "provider_user_id": str(userinfo.get("id", "")),
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": avatar_url,
        "given_name": name.split(" ")[0] if name and " " in name else name,
        "family_name": " ".join(name.split(" ")[1:]) if name and " " in name else "",
    }


def find_user_by_provider(
    provider: str, provider_user_id: str
) -> Optional[Dict[str, Any]]:
    """Find user by OAuth provider and provider user ID

    Args:
        provider: OAuth provider name
        provider_user_id: Provider's user ID

    Returns:
        User document or None
    """
    try:
        return users_collection.find_one(
            {
                "auth_providers.provider": provider,
                "auth_providers.provider_user_id": provider_user_id,
            }
        )
    except Exception:
        return None


def create_oauth_user(provider_info: Dict[str, Any], provider: str) -> Optional[str]:
    """Create a new user from OAuth provider information

    Args:
        provider_info: Standardized provider info
        provider: Provider name

    Returns:
        User ID string or None if creation failed
    """
    try:
        now = datetime.now(timezone.utc)

        user_doc = {
            "email": provider_info["email"],
            "email_verified": provider_info["email_verified"],
            "user_name": provider_info["name"] or provider_info["email"].split("@")[0],
            "pfp": {
                "url": provider_info["picture"],
                "source": provider,
                "last_updated": now,
            }
            if provider_info["picture"]
            else None,
            "password_hash": None,
            "password_set": False,
            "auth_providers": [
                {
                    "provider": provider,
                    "provider_user_id": provider_info["provider_user_id"],
                    "email": provider_info["email"],
                    "email_verified": provider_info["email_verified"],
                    "profile": {
                        "name": provider_info["name"],
                        "picture": provider_info["picture"],
                    },
                    "linked_at": now,
                }
            ],
            "plan": "free",
            "signup_ip": get_client_ip(),
            "created_at": now,
            "updated_at": now,
            "last_login_at": now,
            "status": "ACTIVE",
        }

        result = users_collection.insert_one(user_doc)
        return str(result.inserted_id)
    except Exception as e:
        log.error(
            "oauth_user_creation_failed",
            provider_id=provider_info.get("provider_user_id"),
            provider=provider_info.get("provider"),
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def link_provider_to_user(
    user_id: str, provider_info: Dict[str, Any], provider: str
) -> bool:
    """Link an OAuth provider to an existing user account

    Args:
        user_id: User's ID
        provider_info: Standardized provider info
        provider: Provider name

    Returns:
        True if linking succeeded, False otherwise
    """
    try:
        from bson import ObjectId

        now = datetime.now(timezone.utc)

        provider_entry = {
            "provider": provider,
            "provider_user_id": provider_info["provider_user_id"],
            "email": provider_info["email"],
            "email_verified": provider_info["email_verified"],
            "profile": {
                "name": provider_info["name"],
                "picture": provider_info["picture"],
            },
            "linked_at": now,
        }

        # Update user document
        update_data = {
            "$push": {"auth_providers": provider_entry},
            "$set": {"updated_at": now, "last_login_at": now},
        }

        # Update profile picture if user doesn't have one or if they prefer provider's picture
        if provider_info["picture"]:
            update_data["$set"]["pfp"] = {
                "url": provider_info["picture"],
                "source": provider,
                "last_updated": now,
            }

        # If email was not verified before but provider verifies it, update verification status
        if provider_info["email_verified"]:
            update_data["$set"]["email_verified"] = True

        result = users_collection.update_one({"_id": ObjectId(user_id)}, update_data)

        return result.modified_count > 0
    except Exception as e:
        log.error(
            "oauth_provider_link_failed",
            user_id=user_id,
            provider=provider,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


def can_auto_link_accounts(
    existing_user: Dict[str, Any], provider_info: Dict[str, Any], provider: str
) -> bool:
    """Determine if we can automatically link accounts based on email verification

    Args:
        existing_user: Existing user document
        provider_info: Provider info from OAuth
        provider: Provider name

    Returns:
        True if accounts can be auto-linked
    """
    # Only auto-link if:
    # 1. Provider email is verified
    # 2. Emails match exactly
    # 3. User doesn't already have this provider linked

    if not provider_info.get("email_verified", False):
        return False

    if existing_user.get("email", "").lower() != provider_info.get("email", "").lower():
        return False

    # Check if provider is already linked
    auth_providers = existing_user.get("auth_providers", [])
    for provider_entry in auth_providers:
        if provider_entry.get("provider") == provider:
            return False

    return True


def update_user_last_login(user_id: str) -> None:
    """Update user's last login timestamp

    Args:
        user_id: User's ID
    """
    try:
        from bson import ObjectId

        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login_at": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        log.error(
            "oauth_last_login_update_failed",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )


def get_oauth_redirect_url(provider: str, action: str = "login") -> str:
    """Generate OAuth redirect URL for the given provider

    First checks for environment variable {PROVIDER}_OAUTH_REDIRECT_URI,
    then falls back to dynamic generation using Flask's url_for.

    Args:
        provider: OAuth provider name
        action: Action being performed ('login' or 'link')

    Returns:
        Full redirect URL
    """
    # Check for environment variable first
    env_var_name = f"{provider.upper()}_OAUTH_REDIRECT_URI"
    env_redirect_uri = os.getenv(env_var_name)

    if env_redirect_uri:
        return env_redirect_uri

    # Fall back to dynamic generation.
    # The generic callback route accepts the provider as a URL parameter,
    # so no changes here are needed when a new provider is added.
    return url_for("oauth.oauth_callback", provider=provider, _external=True)
