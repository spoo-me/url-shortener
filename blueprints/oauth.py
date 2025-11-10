from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, g, redirect

from .limiter import limiter
from utils.auth_utils import (
    generate_access_jwt,
    generate_refresh_jwt,
    set_refresh_cookie,
    set_access_cookie,
    requires_auth,
)
from utils.mongo_utils import (
    get_user_by_email,
    get_user_by_id,
    users_collection,
)
from utils.oauth_utils import (
    init_oauth,
    generate_oauth_state,
    verify_oauth_state,
    extract_user_info_from_google,
    extract_user_info_from_github,
    extract_user_info_from_discord,
    find_user_by_provider,
    create_oauth_user,
    link_provider_to_user,
    can_auto_link_accounts,
    update_user_last_login,
    get_oauth_redirect_url,
    OAuthProviders,
)


oauth_bp = Blueprint("oauth", __name__)


# Initialize OAuth - this needs to be done at the app level
oauth = None
providers = {}


def init_oauth_for_app(app):
    """Initialize OAuth with the Flask app"""
    global oauth, providers
    oauth, providers = init_oauth(app)
    return oauth, providers


@oauth_bp.route("/google", methods=["GET"])
@limiter.limit("10/minute")
def oauth_google_login():
    """Initiate Google OAuth login"""
    google = providers.get("google")
    if not google:
        return jsonify({"error": "Google OAuth not configured"}), 500

    # Generate state parameter for CSRF protection
    state = generate_oauth_state(OAuthProviders.GOOGLE, "login")

    # Get redirect URI
    redirect_uri = get_oauth_redirect_url(OAuthProviders.GOOGLE)

    # Redirect to Google OAuth
    return google.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/google/callback", methods=["GET"])
@limiter.limit("20/minute")
def oauth_google_callback():
    """Handle Google OAuth callback"""
    google = providers.get("google")
    if not google:
        return jsonify({"error": "Google OAuth not configured"}), 500

    # Verify state parameter
    state = request.args.get("state")
    if not state:
        return jsonify({"error": "missing state parameter"}), 400

    is_valid, state_data = verify_oauth_state(state, OAuthProviders.GOOGLE)
    if not is_valid:
        return jsonify({"error": "invalid state parameter"}), 400

    # Check for error from OAuth provider
    error = request.args.get("error")
    if error:
        error_description = request.args.get(
            "error_description", "OAuth authorization failed"
        )
        return jsonify({"error": f"OAuth error: {error_description}"}), 400

    try:
        # Exchange authorization code for token
        token = google.authorize_access_token()

        # Get user info from Google
        userinfo = token.get("userinfo")
        if not userinfo:
            # Fallback: fetch userinfo manually
            resp = google.get("userinfo", token=token)
            userinfo = resp.json()

        # Extract standardized user info
        provider_info = extract_user_info_from_google(userinfo)

        if not provider_info["email"]:
            return jsonify({"error": "email not provided by OAuth provider"}), 400

        # Check if this is a linking action
        action = state_data.get("action", "login")

        if action == "link":
            # This is an account linking request
            link_user_id = state_data.get("user_id")
            if not link_user_id:
                return jsonify({"error": "invalid linking request"}), 400

            # Verify user exists
            current_user = get_user_by_id(link_user_id)
            if not current_user:
                return jsonify({"error": "user not found"}), 404

            # Check if provider is already linked to this user
            auth_providers = current_user.get("auth_providers", [])
            for provider_entry in auth_providers:
                if provider_entry.get("provider") == OAuthProviders.GOOGLE:
                    return jsonify({"error": "Google account already linked"}), 409

            # Check if this Google account is already linked to another user
            existing_oauth_user = find_user_by_provider(
                OAuthProviders.GOOGLE, provider_info["provider_user_id"]
            )
            if existing_oauth_user and str(existing_oauth_user["_id"]) != link_user_id:
                return jsonify(
                    {"error": "This Google account is already linked to another user"}
                ), 409

            # Verify that the OAuth email matches the current user's email
            if current_user.get("email", "").lower() != provider_info["email"].lower():
                return jsonify(
                    {
                        "error": "email mismatch",
                        "message": f"The email associated with this Google account ({provider_info['email']}) does not match your account email ({current_user.get('email', '')}). Please use a Google account with the same email address.",
                    }
                ), 400

            # Link the provider to current user
            if link_provider_to_user(
                link_user_id, provider_info, OAuthProviders.GOOGLE
            ):
                # Generate tokens for the linked user
                auth_method = OAuthProviders.GOOGLE
                access_token = generate_access_jwt(link_user_id, auth_method)
                refresh_token = generate_refresh_jwt(link_user_id, auth_method)

                # Set tokens in cookies and redirect
                resp = redirect("/dashboard")
                set_refresh_cookie(resp, refresh_token)
                set_access_cookie(resp, access_token)
                return resp
            else:
                return jsonify({"error": "failed to link Google account"}), 500

        # Check if user already exists with this OAuth provider
        existing_oauth_user = find_user_by_provider(
            OAuthProviders.GOOGLE, provider_info["provider_user_id"]
        )

        if existing_oauth_user:
            # User exists with this OAuth provider - log them in
            user_id = str(existing_oauth_user["_id"])
            update_user_last_login(user_id)

            # Generate tokens
            auth_method = OAuthProviders.GOOGLE
            access_token = generate_access_jwt(user_id, auth_method)
            refresh_token = generate_refresh_jwt(user_id, auth_method)

            # Set tokens in cookies and redirect
            resp = redirect("/dashboard")
            set_refresh_cookie(resp, refresh_token)
            set_access_cookie(resp, access_token)
            return resp

        # Check if user exists with the same email
        existing_email_user = get_user_by_email(provider_info["email"])

        if existing_email_user:
            # User exists with same email - check if we can auto-link
            if can_auto_link_accounts(
                existing_email_user, provider_info, OAuthProviders.GOOGLE
            ):
                # Auto-link the accounts
                user_id = str(existing_email_user["_id"])

                if link_provider_to_user(user_id, provider_info, OAuthProviders.GOOGLE):
                    update_user_last_login(user_id)

                    # Generate tokens
                    auth_method = OAuthProviders.GOOGLE
                    access_token = generate_access_jwt(user_id, auth_method)
                    refresh_token = generate_refresh_jwt(user_id, auth_method)

                    # Set tokens in cookies and redirect
                    resp = redirect("/dashboard")
                    set_refresh_cookie(resp, refresh_token)
                    set_access_cookie(resp, access_token)
                    return resp
                else:
                    return jsonify({"error": "failed to link accounts"}), 500
            else:
                # Cannot auto-link - require manual account linking or different email
                return jsonify(
                    {
                        "error": "email already exists",
                        "message": "An account with this email already exists. Please log in with your existing method first to link accounts.",
                    }
                ), 409

        # Create new user with OAuth
        user_id = create_oauth_user(provider_info, OAuthProviders.GOOGLE)

        if not user_id:
            return jsonify({"error": "failed to create user"}), 500

        # Generate tokens
        auth_method = OAuthProviders.GOOGLE
        access_token = generate_access_jwt(user_id, auth_method)
        refresh_token = generate_refresh_jwt(user_id, auth_method)

        # Set tokens in cookies and redirect
        resp = redirect("/dashboard")
        set_refresh_cookie(resp, refresh_token)
        set_access_cookie(resp, access_token)
        return resp

    except Exception as e:
        print(f"OAuth callback error: {e}")
        return jsonify({"error": "OAuth authentication failed"}), 500


@oauth_bp.route("/google/link", methods=["GET"])
@requires_auth
@limiter.limit("5/minute")
def oauth_google_link():
    """Link Google OAuth to existing account"""
    google = providers.get("google")
    if not google:
        return jsonify({"error": "Google OAuth not configured"}), 500

    # Check if user already has Google linked
    current_user = get_user_by_id(g.user_id)
    if not current_user:
        return jsonify({"error": "user not found"}), 404

    auth_providers = current_user.get("auth_providers", [])
    for provider_entry in auth_providers:
        if provider_entry.get("provider") == OAuthProviders.GOOGLE:
            return jsonify({"error": "Google account already linked"}), 409

    # Generate state parameter for CSRF protection with user ID embedded securely
    state = generate_oauth_state(OAuthProviders.GOOGLE, "link", user_id=str(g.user_id))

    # Get redirect URI (same as login)
    redirect_uri = get_oauth_redirect_url(OAuthProviders.GOOGLE)

    # Redirect to Google OAuth
    return google.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/github", methods=["GET"])
@limiter.limit("10/minute")
def oauth_github_login():
    """Initiate GitHub OAuth login"""
    github = providers.get("github")
    if not github:
        return jsonify({"error": "GitHub OAuth not configured"}), 500

    # Generate state parameter for CSRF protection
    state = generate_oauth_state(OAuthProviders.GITHUB, "login")

    # Get redirect URI
    redirect_uri = get_oauth_redirect_url(OAuthProviders.GITHUB)

    # Redirect to GitHub OAuth
    return github.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/github/callback", methods=["GET"])
@limiter.limit("20/minute")
def oauth_github_callback():
    """Handle GitHub OAuth callback"""
    github = providers.get("github")
    if not github:
        return jsonify({"error": "GitHub OAuth not configured"}), 500

    # Verify state parameter
    state = request.args.get("state")
    if not state:
        return jsonify({"error": "missing state parameter"}), 400

    is_valid, state_data = verify_oauth_state(state, OAuthProviders.GITHUB)
    if not is_valid:
        return jsonify({"error": "invalid state parameter"}), 400

    # Check for error from OAuth provider
    error = request.args.get("error")
    if error:
        error_description = request.args.get(
            "error_description", "OAuth authorization failed"
        )
        return jsonify({"error": f"OAuth error: {error_description}"}), 400

    try:
        # Exchange authorization code for token
        token = github.authorize_access_token()

        # Get user info from GitHub
        resp = github.get("user", token=token)
        userinfo = resp.json()

        # Get user emails from GitHub
        emails_resp = github.get("user/emails", token=token)
        email_data = emails_resp.json()

        # Extract standardized user info
        provider_info = extract_user_info_from_github(userinfo, email_data)

        if not provider_info["email"]:
            return jsonify({"error": "email not provided by OAuth provider"}), 400

        # Check if this is a linking action
        action = state_data.get("action", "login")

        if action == "link":
            # This is an account linking request
            link_user_id = state_data.get("user_id")
            if not link_user_id:
                return jsonify({"error": "invalid linking request"}), 400

            # Verify user exists
            current_user = get_user_by_id(link_user_id)
            if not current_user:
                return jsonify({"error": "user not found"}), 404

            # Check if provider is already linked to this user
            auth_providers = current_user.get("auth_providers", [])
            for provider_entry in auth_providers:
                if provider_entry.get("provider") == OAuthProviders.GITHUB:
                    return jsonify({"error": "GitHub account already linked"}), 409

            # Check if this GitHub account is already linked to another user
            existing_oauth_user = find_user_by_provider(
                OAuthProviders.GITHUB, provider_info["provider_user_id"]
            )
            if existing_oauth_user and str(existing_oauth_user["_id"]) != link_user_id:
                return jsonify(
                    {"error": "This GitHub account is already linked to another user"}
                ), 409

            # Verify that the OAuth email matches the current user's email
            if current_user.get("email", "").lower() != provider_info["email"].lower():
                return jsonify(
                    {
                        "error": "email mismatch",
                        "message": f"The email associated with this GitHub account ({provider_info['email']}) does not match your account email ({current_user.get('email', '')}). Please use a GitHub account with the same email address.",
                    }
                ), 400

            # Link the provider to current user
            if link_provider_to_user(
                link_user_id, provider_info, OAuthProviders.GITHUB
            ):
                # Generate tokens for the linked user
                auth_method = OAuthProviders.GITHUB
                access_token = generate_access_jwt(link_user_id, auth_method)
                refresh_token = generate_refresh_jwt(link_user_id, auth_method)

                # Set tokens in cookies and redirect
                resp = redirect("/dashboard")
                set_refresh_cookie(resp, refresh_token)
                set_access_cookie(resp, access_token)
                return resp
            else:
                return jsonify({"error": "failed to link GitHub account"}), 500

        # Check if user already exists with this OAuth provider
        existing_oauth_user = find_user_by_provider(
            OAuthProviders.GITHUB, provider_info["provider_user_id"]
        )

        if existing_oauth_user:
            # User exists with this OAuth provider - log them in
            user_id = str(existing_oauth_user["_id"])
            update_user_last_login(user_id)

            # Generate tokens
            auth_method = OAuthProviders.GITHUB
            access_token = generate_access_jwt(user_id, auth_method)
            refresh_token = generate_refresh_jwt(user_id, auth_method)

            # Set tokens in cookies and redirect
            resp = redirect("/dashboard")
            set_refresh_cookie(resp, refresh_token)
            set_access_cookie(resp, access_token)
            return resp

        # Check if user exists with the same email
        existing_email_user = get_user_by_email(provider_info["email"])

        if existing_email_user:
            # User exists with same email - check if we can auto-link
            if can_auto_link_accounts(
                existing_email_user, provider_info, OAuthProviders.GITHUB
            ):
                # Auto-link the accounts
                user_id = str(existing_email_user["_id"])

                if link_provider_to_user(user_id, provider_info, OAuthProviders.GITHUB):
                    update_user_last_login(user_id)

                    # Generate tokens
                    auth_method = OAuthProviders.GITHUB
                    access_token = generate_access_jwt(user_id, auth_method)
                    refresh_token = generate_refresh_jwt(user_id, auth_method)

                    # Set tokens in cookies and redirect
                    resp = redirect("/dashboard")
                    set_refresh_cookie(resp, refresh_token)
                    set_access_cookie(resp, access_token)
                    return resp
                else:
                    return jsonify({"error": "failed to link accounts"}), 500
            else:
                # Cannot auto-link - require manual account linking or different email
                return jsonify(
                    {
                        "error": "email already exists",
                        "message": "An account with this email already exists. Please log in with your existing method first to link accounts.",
                    }
                ), 409

        # Create new user with OAuth
        user_id = create_oauth_user(provider_info, OAuthProviders.GITHUB)

        if not user_id:
            return jsonify({"error": "failed to create user"}), 500

        # Generate tokens
        auth_method = OAuthProviders.GITHUB
        access_token = generate_access_jwt(user_id, auth_method)
        refresh_token = generate_refresh_jwt(user_id, auth_method)

        # Set tokens in cookies and redirect
        resp = redirect("/dashboard")
        set_refresh_cookie(resp, refresh_token)
        set_access_cookie(resp, access_token)
        return resp

    except Exception as e:
        print(f"GitHub OAuth callback error: {e}")
        return jsonify({"error": "OAuth authentication failed"}), 500


@oauth_bp.route("/github/link", methods=["GET"])
@requires_auth
@limiter.limit("5/minute")
def oauth_github_link():
    """Link GitHub OAuth to existing account"""
    github = providers.get("github")
    if not github:
        return jsonify({"error": "GitHub OAuth not configured"}), 500

    # Check if user already has GitHub linked
    current_user = get_user_by_id(g.user_id)
    if not current_user:
        return jsonify({"error": "user not found"}), 404

    auth_providers = current_user.get("auth_providers", [])
    for provider_entry in auth_providers:
        if provider_entry.get("provider") == OAuthProviders.GITHUB:
            return jsonify({"error": "GitHub account already linked"}), 409

    # Generate state parameter for CSRF protection with user ID embedded securely
    state = generate_oauth_state(OAuthProviders.GITHUB, "link", user_id=str(g.user_id))

    # Get redirect URI (same as login)
    redirect_uri = get_oauth_redirect_url(OAuthProviders.GITHUB)

    # Redirect to GitHub OAuth
    return github.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/discord", methods=["GET"])
@limiter.limit("10/minute")
def oauth_discord_login():
    """Initiate Discord OAuth login"""
    discord = providers.get("discord")
    if not discord:
        return jsonify({"error": "Discord OAuth not configured"}), 500

    # Generate state parameter for CSRF protection
    state = generate_oauth_state(OAuthProviders.DISCORD, "login")

    # Get redirect URI
    redirect_uri = get_oauth_redirect_url(OAuthProviders.DISCORD)

    # Redirect to Discord OAuth
    return discord.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/discord/callback", methods=["GET"])
@limiter.limit("20/minute")
def oauth_discord_callback():
    """Handle Discord OAuth callback"""
    discord = providers.get("discord")
    if not discord:
        return jsonify({"error": "Discord OAuth not configured"}), 500

    # Verify state parameter
    state = request.args.get("state")
    if not state:
        return jsonify({"error": "missing state parameter"}), 400

    is_valid, state_data = verify_oauth_state(state, OAuthProviders.DISCORD)
    if not is_valid:
        return jsonify({"error": "invalid state parameter"}), 400

    # Check for error from OAuth provider
    error = request.args.get("error")
    if error:
        error_description = request.args.get(
            "error_description", "OAuth authorization failed"
        )
        return jsonify({"error": f"OAuth error: {error_description}"}), 400

    try:
        # Exchange authorization code for token
        token = discord.authorize_access_token()

        # Get user info from Discord
        resp = discord.get("users/@me", token=token)
        userinfo = resp.json()

        # Extract standardized user info
        provider_info = extract_user_info_from_discord(userinfo)

        if not provider_info["email"]:
            return jsonify({"error": "email not provided by OAuth provider"}), 400

        # Check if this is a linking action
        action = state_data.get("action", "login")

        if action == "link":
            # This is an account linking request
            link_user_id = state_data.get("user_id")
            if not link_user_id:
                return jsonify({"error": "invalid linking request"}), 400

            # Verify user exists
            current_user = get_user_by_id(link_user_id)
            if not current_user:
                return jsonify({"error": "user not found"}), 404

            # Check if provider is already linked to this user
            auth_providers = current_user.get("auth_providers", [])
            for provider_entry in auth_providers:
                if provider_entry.get("provider") == OAuthProviders.DISCORD:
                    return jsonify({"error": "Discord account already linked"}), 409

            # Check if this Discord account is already linked to another user
            existing_oauth_user = find_user_by_provider(
                OAuthProviders.DISCORD, provider_info["provider_user_id"]
            )
            if existing_oauth_user and str(existing_oauth_user["_id"]) != link_user_id:
                return jsonify(
                    {"error": "This Discord account is already linked to another user"}
                ), 409

            # Verify that the OAuth email matches the current user's email
            if current_user.get("email", "").lower() != provider_info["email"].lower():
                return jsonify(
                    {
                        "error": "email mismatch",
                        "message": f"The email associated with this Discord account ({provider_info['email']}) does not match your account email ({current_user.get('email', '')}). Please use a Discord account with the same email address.",
                    }
                ), 400

            # Link the provider to current user
            if link_provider_to_user(
                link_user_id, provider_info, OAuthProviders.DISCORD
            ):
                # Generate tokens for the linked user
                auth_method = OAuthProviders.DISCORD
                access_token = generate_access_jwt(link_user_id, auth_method)
                refresh_token = generate_refresh_jwt(link_user_id, auth_method)

                # Set tokens in cookies and redirect
                resp = redirect("/dashboard")
                set_refresh_cookie(resp, refresh_token)
                set_access_cookie(resp, access_token)
                return resp
            else:
                return jsonify({"error": "failed to link Discord account"}), 500

        # Check if user already exists with this OAuth provider
        existing_oauth_user = find_user_by_provider(
            OAuthProviders.DISCORD, provider_info["provider_user_id"]
        )

        if existing_oauth_user:
            # User exists with this OAuth provider - log them in
            user_id = str(existing_oauth_user["_id"])
            update_user_last_login(user_id)

            # Generate tokens
            auth_method = OAuthProviders.DISCORD
            access_token = generate_access_jwt(user_id, auth_method)
            refresh_token = generate_refresh_jwt(user_id, auth_method)

            # Set tokens in cookies and redirect
            resp = redirect("/dashboard")
            set_refresh_cookie(resp, refresh_token)
            set_access_cookie(resp, access_token)
            return resp

        # Check if user exists with the same email
        existing_email_user = get_user_by_email(provider_info["email"])

        if existing_email_user:
            # User exists with same email - check if we can auto-link
            if can_auto_link_accounts(
                existing_email_user, provider_info, OAuthProviders.DISCORD
            ):
                # Auto-link the accounts
                user_id = str(existing_email_user["_id"])

                if link_provider_to_user(
                    user_id, provider_info, OAuthProviders.DISCORD
                ):
                    update_user_last_login(user_id)

                    # Generate tokens
                    auth_method = OAuthProviders.DISCORD
                    access_token = generate_access_jwt(user_id, auth_method)
                    refresh_token = generate_refresh_jwt(user_id, auth_method)

                    # Set tokens in cookies and redirect
                    resp = redirect("/dashboard")
                    set_refresh_cookie(resp, refresh_token)
                    set_access_cookie(resp, access_token)
                    return resp
                else:
                    return jsonify({"error": "failed to link accounts"}), 500
            else:
                # Cannot auto-link - require manual account linking or different email
                return jsonify(
                    {
                        "error": "email already exists",
                        "message": "An account with this email already exists. Please log in with your existing method first to link accounts.",
                    }
                ), 409

        # Create new user with OAuth
        user_id = create_oauth_user(provider_info, OAuthProviders.DISCORD)

        if not user_id:
            return jsonify({"error": "failed to create user"}), 500

        # Generate tokens
        auth_method = OAuthProviders.DISCORD
        access_token = generate_access_jwt(user_id, auth_method)
        refresh_token = generate_refresh_jwt(user_id, auth_method)

        # Set tokens in cookies and redirect
        resp = redirect("/dashboard")
        set_refresh_cookie(resp, refresh_token)
        set_access_cookie(resp, access_token)
        return resp

    except Exception as e:
        print(f"Discord OAuth callback error: {e}")
        return jsonify({"error": "OAuth authentication failed"}), 500


@oauth_bp.route("/discord/link", methods=["GET"])
@requires_auth
@limiter.limit("5/minute")
def oauth_discord_link():
    """Link Discord OAuth to existing account"""
    discord = providers.get("discord")
    if not discord:
        return jsonify({"error": "Discord OAuth not configured"}), 500

    # Check if user already has Discord linked
    current_user = get_user_by_id(g.user_id)
    if not current_user:
        return jsonify({"error": "user not found"}), 404

    auth_providers = current_user.get("auth_providers", [])
    for provider_entry in auth_providers:
        if provider_entry.get("provider") == OAuthProviders.DISCORD:
            return jsonify({"error": "Discord account already linked"}), 409

    # Generate state parameter for CSRF protection with user ID embedded securely
    state = generate_oauth_state(OAuthProviders.DISCORD, "link", user_id=str(g.user_id))

    # Get redirect URI (same as login)
    redirect_uri = get_oauth_redirect_url(OAuthProviders.DISCORD)

    # Redirect to Discord OAuth
    return discord.authorize_redirect(redirect_uri, state=state)


@oauth_bp.route("/providers", methods=["GET"])
@requires_auth
def list_auth_providers():
    """List all linked OAuth providers for the current user"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    providers = []
    for provider in user.get("auth_providers", []):
        providers.append(
            {
                "provider": provider.get("provider"),
                "email": provider.get("email"),
                "email_verified": provider.get("email_verified", False),
                "linked_at": provider.get("linked_at").isoformat()
                if provider.get("linked_at")
                else None,
                "profile": {
                    "name": provider.get("profile", {}).get("name"),
                    "picture": provider.get("profile", {}).get("picture"),
                },
            }
        )

    return jsonify(
        {"providers": providers, "password_set": user.get("password_set", False)}
    )


@oauth_bp.route("/providers/<provider>/unlink", methods=["DELETE"])
@requires_auth
@limiter.limit("5/minute")
def unlink_oauth_provider(provider):
    """Unlink an OAuth provider from the current user"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    # Check if user has password or other providers
    auth_providers = user.get("auth_providers", [])
    has_password = user.get("password_set", False)

    # Count providers after removing this one
    remaining_providers = [p for p in auth_providers if p.get("provider") != provider]

    if not has_password and len(remaining_providers) == 0:
        return jsonify(
            {
                "error": "cannot unlink last authentication method",
                "message": "Set a password first before unlinking your last OAuth provider",
            }
        ), 400

    # Remove the provider
    try:
        from bson import ObjectId

        result = users_collection.update_one(
            {"_id": ObjectId(g.user_id)},
            {
                "$pull": {"auth_providers": {"provider": provider}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        if result.modified_count > 0:
            return jsonify(
                {"success": True, "message": f"{provider} unlinked successfully"}
            )
        else:
            return jsonify({"error": "provider not found or already unlinked"}), 404

    except Exception as e:
        print(f"Error unlinking provider: {e}")
        return jsonify({"error": "failed to unlink provider"}), 500
