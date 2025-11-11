from flask import Blueprint, jsonify, request, g, render_template, redirect
from datetime import datetime, timezone
from bson import ObjectId

from utils.auth_utils import (
    requires_auth,
)
from utils.mongo_utils import (
    get_user_by_id,
    users_collection,
)
from utils.auth_utils import get_user_profile
from blueprints.limiter import limiter, rate_limit_key_for_request


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@limiter.limit("60 per minute", key_func=rate_limit_key_for_request)
@requires_auth
def dashboard():
    # Redirect to links page as the default dashboard view
    return redirect("/dashboard/links")


@dashboard_bp.route("/links", methods=["GET"])
@requires_auth
@limiter.limit("60 per minute", key_func=rate_limit_key_for_request)
def dashboard_links():
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return render_template(
        "dashboard/links.html",
        host_url=request.host_url,
        user=get_user_profile(user),
    )


@dashboard_bp.route("/keys", methods=["GET"])
@limiter.limit("60 per minute", key_func=rate_limit_key_for_request)
@requires_auth
def dashboard_keys():
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return render_template(
        "dashboard/keys.html",
        host_url=request.host_url,
        user=get_user_profile(user),
    )


@dashboard_bp.route("/statistics", methods=["GET"])
@requires_auth
@limiter.limit(
    "60 per minute", key_func=rate_limit_key_for_request
)  # same as authenticated limit in stats API
def dashboard_statistics():
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return render_template(
        "dashboard/statistics.html",
        host_url=request.host_url,
        user=get_user_profile(user),
    )


@dashboard_bp.route("/settings", methods=["GET"])
@requires_auth
@limiter.limit("60 per minute", key_func=rate_limit_key_for_request)
def dashboard_settings():
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return render_template(
        "dashboard/settings.html",
        host_url=request.host_url,
        user=get_user_profile(user),
    )


@dashboard_bp.route("/billing", methods=["GET"])
@requires_auth
@limiter.limit("60 per minute", key_func=rate_limit_key_for_request)
def dashboard_billing():
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return render_template(
        "dashboard/billing.html",
        host_url=request.host_url,
        user=get_user_profile(user),
    )


@dashboard_bp.route("/profile-pictures", methods=["GET"])
@limiter.limit("30 per minute", key_func=rate_limit_key_for_request)
@requires_auth
def get_profile_pictures():
    """Get available profile pictures from connected OAuth providers"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    pictures = []
    current_pfp_url = user.get("pfp", {}).get("url")

    # Get pictures from OAuth providers
    for provider in user.get("auth_providers", []):
        picture_url = provider.get("profile", {}).get("picture")
        if picture_url:
            pictures.append(
                {
                    "id": f"{provider.get('provider')}_{provider.get('provider_user_id')}",
                    "url": picture_url,
                    "source": provider.get("provider"),
                    "is_current": current_pfp_url == picture_url,
                }
            )

    return jsonify({"pictures": pictures})


@dashboard_bp.route("/profile-pictures", methods=["POST"])
@limiter.limit("5 per minute", key_func=rate_limit_key_for_request)
@requires_auth
def set_profile_picture():
    """Set user's profile picture from available options"""
    data = request.get_json()
    if not data or "picture_id" not in data:
        return jsonify({"error": "picture_id is required"}), 400

    picture_id = data["picture_id"]
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    # Find the picture from OAuth providers
    for provider in user.get("auth_providers", []):
        provider_id = f"{provider.get('provider')}_{provider.get('provider_user_id')}"
        if provider_id == picture_id:
            picture_url = provider.get("profile", {}).get("picture")
            if picture_url:
                # Update user's profile picture
                result = users_collection.update_one(
                    {"_id": ObjectId(g.user_id)},
                    {
                        "$set": {
                            "pfp": {
                                "url": picture_url,
                                "source": provider.get("provider"),
                                "last_updated": datetime.now(timezone.utc),
                            }
                        }
                    },
                )

                # Check if the update was successful (idempotent)
                if not result.acknowledged:
                    return jsonify({"error": "Failed to update profile picture"}), 500
                if result.matched_count == 0:
                    return jsonify({"error": "user not found"}), 404
                return jsonify({"message": "Profile picture updated successfully"})

    return jsonify({"error": "Picture not found"}), 404
