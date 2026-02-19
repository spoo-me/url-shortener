from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify, redirect, request
from bson import ObjectId

from .limiter import limiter
from .limits import Limits
from utils.auth_utils import (
    generate_access_jwt,
    generate_refresh_jwt,
    requires_auth,
    set_access_cookie,
    set_refresh_cookie,
)
from utils.email_service import email_service
from utils.logger import get_logger
from utils.mongo_utils import get_user_by_email, get_user_by_id, users_collection
from utils.oauth_providers import PROVIDER_STRATEGIES, OAuthProviderStrategy
from utils.oauth_utils import (
    can_auto_link_accounts,
    create_oauth_user,
    find_user_by_provider,
    generate_oauth_state,
    get_oauth_redirect_url,
    init_oauth,
    link_provider_to_user,
    update_user_last_login,
    verify_oauth_state,
)

oauth_bp = Blueprint("oauth", __name__)
log = get_logger(__name__)

# Single source of truth for the post-auth redirect destination.
DASHBOARD_URL = "/dashboard"

# Populated by init_oauth_for_app() at startup; keyed by provider name.
_providers: dict = {}


def init_oauth_for_app(app):
    """Initialize OAuth with the Flask app."""
    global _providers
    oauth, _providers = init_oauth(app)
    return oauth, _providers


# Private helpers


def _get_client(provider: str):
    """Return the Authlib client for *provider*, or None if not configured."""
    return _providers.get(provider)


def _make_auth_response(user_id: str, provider_key: str) -> Response:
    """Generate JWT tokens and return a redirect response to the dashboard."""
    access_token = generate_access_jwt(user_id, True, provider_key)
    refresh_token = generate_refresh_jwt(user_id, True, provider_key)
    resp = redirect(DASHBOARD_URL)
    set_refresh_cookie(resp, refresh_token)
    set_access_cookie(resp, access_token)
    return resp


def _handle_callback(
    strategy: OAuthProviderStrategy, client, provider_key: str
) -> Response:
    """Shared OAuth callback logic — runs identically for every provider.

    Steps:
        1. Validate the state parameter (CSRF protection).
        2. Check for an error response from the provider.
        3. Exchange the authorisation code for a token and fetch user info.
        4. Route to: account-link, existing-login, auto-link, or new-user.
    """
    # State validation
    state = request.args.get("state")
    if not state:
        log.warning("oauth_state_missing", provider=provider_key)
        return jsonify({"error": "missing state parameter"}), 400

    is_valid, state_data = verify_oauth_state(state, provider_key)
    if not is_valid:
        log.warning("oauth_state_invalid", provider=provider_key)
        return jsonify({"error": "invalid state parameter"}), 400

    # Provider-reported error
    error = request.args.get("error")
    if error:
        error_description = request.args.get(
            "error_description", "OAuth authorization failed"
        )
        log.warning(
            "oauth_provider_error",
            provider=provider_key,
            error=error,
            description=error_description,
        )
        return jsonify({"error": f"OAuth error: {error_description}"}), 400

    try:
        # Token exchange + provider-specific user-info fetch
        token = client.authorize_access_token()
        provider_info = strategy.fetch_user_info(client, token)

        if not provider_info["email"]:
            return jsonify({"error": "email not provided by OAuth provider"}), 400

        action = state_data.get("action", "login")
        provider_display = provider_key.title()

        # Account-linking flow
        if action == "link":
            link_user_id = state_data.get("user_id")
            if not link_user_id:
                return jsonify({"error": "invalid linking request"}), 400

            current_user = get_user_by_id(link_user_id)
            if not current_user:
                return jsonify({"error": "user not found"}), 404

            for entry in current_user.get("auth_providers", []):
                if entry.get("provider") == provider_key:
                    return (
                        jsonify(
                            {"error": f"{provider_display} account already linked"}
                        ),
                        409,
                    )

            existing_oauth_user = find_user_by_provider(
                provider_key, provider_info["provider_user_id"]
            )
            if existing_oauth_user and str(existing_oauth_user["_id"]) != link_user_id:
                return (
                    jsonify(
                        {
                            "error": f"This {provider_display} account is already linked to another user"
                        }
                    ),
                    409,
                )

            if current_user.get("email", "").lower() != provider_info["email"].lower():
                log.warning(
                    "oauth_email_mismatch",
                    user_id=link_user_id,
                    provider=provider_key,
                    reason="linking_attempt",
                )
                return (
                    jsonify(
                        {
                            "error": "email mismatch",
                            "message": (
                                f"The email associated with this {provider_display} account "
                                f"({provider_info['email']}) does not match your account email "
                                f"({current_user.get('email', '')}). "
                                f"Please use a {provider_display} account with the same email address."
                            ),
                        }
                    ),
                    400,
                )

            if link_provider_to_user(link_user_id, provider_info, provider_key):
                log.info(
                    "oauth_account_linked",
                    user_id=link_user_id,
                    provider=provider_key,
                )
                return _make_auth_response(link_user_id, provider_key)
            else:
                log.error(
                    "oauth_linking_failed",
                    user_id=link_user_id,
                    provider=provider_key,
                    reason="database_error",
                )
                return (
                    jsonify({"error": f"failed to link {provider_display} account"}),
                    500,
                )

        # Existing OAuth user → login
        existing_oauth_user = find_user_by_provider(
            provider_key, provider_info["provider_user_id"]
        )
        if existing_oauth_user:
            user_id = str(existing_oauth_user["_id"])
            update_user_last_login(user_id)
            log.info(
                "oauth_login_success",
                user_id=user_id,
                provider=provider_key,
                action="login",
            )
            return _make_auth_response(user_id, provider_key)

        # Email collision - attempt auto-link or reject
        existing_email_user = get_user_by_email(provider_info["email"])
        if existing_email_user:
            if can_auto_link_accounts(existing_email_user, provider_info, provider_key):
                user_id = str(existing_email_user["_id"])
                if link_provider_to_user(user_id, provider_info, provider_key):
                    update_user_last_login(user_id)
                    log.info(
                        "oauth_auto_linked", user_id=user_id, provider=provider_key
                    )
                    return _make_auth_response(user_id, provider_key)
                else:
                    log.error(
                        "oauth_auto_link_failed",
                        user_id=user_id,
                        provider=provider_key,
                    )
                    return jsonify({"error": "failed to link accounts"}), 500
            else:
                return (
                    jsonify(
                        {
                            "error": "email already exists",
                            "message": "An account with this email already exists. Please log in with your existing method first to link accounts.",
                        }
                    ),
                    409,
                )

        # Brand-new user
        user_id = create_oauth_user(provider_info, provider_key)
        if not user_id:
            log.error("oauth_user_creation_failed", provider=provider_key)
            return jsonify({"error": "failed to create user"}), 500

        log.info(
            "user_registered", user_id=user_id, auth_method=f"{provider_key}_oauth"
        )
        email_service.send_welcome_email(
            provider_info["email"], provider_info.get("name")
        )
        return _make_auth_response(user_id, provider_key)

    except Exception as e:
        log.error(
            "oauth_callback_failed",
            provider=provider_key,
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": "OAuth authentication failed"}), 500


# Generic routes  (/<provider>, /<provider>/callback, /<provider>/link)


@oauth_bp.route("/<provider>", methods=["GET"])
@limiter.limit(Limits.OAUTH_INIT)
def oauth_login(provider: str):
    """Initiate OAuth login for any configured provider."""
    strategy = PROVIDER_STRATEGIES.get(provider)
    client = _get_client(provider)
    if not strategy or not client:
        return jsonify({"error": f"'{provider}' OAuth not configured"}), 404

    state = generate_oauth_state(provider, "login")
    redirect_uri = get_oauth_redirect_url(provider)
    return client.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/<provider>/callback", methods=["GET"])
@limiter.limit(Limits.OAUTH_CALLBACK)
def oauth_callback(provider: str):
    """Handle OAuth callback for any configured provider."""
    strategy = PROVIDER_STRATEGIES.get(provider)
    client = _get_client(provider)
    if not strategy or not client:
        return jsonify({"error": f"'{provider}' OAuth not configured"}), 404

    return _handle_callback(strategy, client, provider)


@oauth_bp.route("/<provider>/link", methods=["GET"])
@requires_auth
@limiter.limit(Limits.OAUTH_LINK)
def oauth_link(provider: str):
    """Link an OAuth provider to the currently authenticated account."""
    strategy = PROVIDER_STRATEGIES.get(provider)
    client = _get_client(provider)
    if not strategy or not client:
        return jsonify({"error": f"'{provider}' OAuth not configured"}), 404

    current_user = get_user_by_id(g.user_id)
    if not current_user:
        return jsonify({"error": "user not found"}), 404

    for entry in current_user.get("auth_providers", []):
        if entry.get("provider") == provider:
            return (
                jsonify({"error": f"{provider.title()} account already linked"}),
                409,
            )

    state = generate_oauth_state(provider, "link", user_id=str(g.user_id))
    redirect_uri = get_oauth_redirect_url(provider)
    return client.authorize_redirect(redirect_uri, state=state)


# Provider management endpoints
@oauth_bp.route("/providers", methods=["GET"])
@requires_auth
def list_auth_providers():
    """List all linked OAuth providers for the current user."""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    linked = [
        {
            "provider": p.get("provider"),
            "email": p.get("email"),
            "email_verified": p.get("email_verified", False),
            "linked_at": p.get("linked_at").isoformat() if p.get("linked_at") else None,
            "profile": {
                "name": p.get("profile", {}).get("name"),
                "picture": p.get("profile", {}).get("picture"),
            },
        }
        for p in user.get("auth_providers", [])
    ]

    return jsonify(
        {"providers": linked, "password_set": user.get("password_set", False)}
    )


@oauth_bp.route("/providers/<provider_name>/unlink", methods=["DELETE"])
@requires_auth
@limiter.limit(Limits.OAUTH_DISCONNECT)
def unlink_oauth_provider(provider_name: str):
    """Unlink an OAuth provider from the current user."""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    auth_providers = user.get("auth_providers", [])
    remaining = [p for p in auth_providers if p.get("provider") != provider_name]

    if not user.get("password_set", False) and len(remaining) == 0:
        return (
            jsonify(
                {
                    "error": "cannot unlink last authentication method",
                    "message": "Set a password first before unlinking your last OAuth provider",
                }
            ),
            400,
        )

    try:
        result = users_collection.update_one(
            {"_id": ObjectId(g.user_id)},
            {
                "$pull": {"auth_providers": {"provider": provider_name}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        if result.modified_count > 0:
            log.info(
                "oauth_provider_unlinked", user_id=g.user_id, provider=provider_name
            )
            return jsonify(
                {"success": True, "message": f"{provider_name} unlinked successfully"}
            )
        else:
            log.warning(
                "oauth_unlink_not_found", user_id=g.user_id, provider=provider_name
            )
            return jsonify({"error": "provider not found or already unlinked"}), 404

    except Exception as e:
        log.error(
            "oauth_unlink_failed",
            user_id=g.user_id,
            provider=provider_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": "failed to unlink provider"}), 500
