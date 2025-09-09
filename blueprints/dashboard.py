from flask import Blueprint, jsonify, request, g, render_template, redirect

from utils.auth_utils import (
    requires_auth,
)
from utils.mongo_utils import (
    get_user_by_id,
)
from utils.auth_utils import get_user_profile


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@requires_auth
def dashboard():
    # Redirect to links page as the default dashboard view
    return redirect("/dashboard/links")


@dashboard_bp.route("/links", methods=["GET"])
@requires_auth
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
def dashboard_settings():
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return render_template(
        "dashboard/settings.html",
        host_url=request.host_url,
        user=get_user_profile(user),
    )
