from flask import Blueprint, render_template, request, redirect
from .limiter import limiter

docs = Blueprint("docs", __name__)


@docs.route("/docs")
@docs.route("/docs/")
@limiter.exempt
def serve_docs_index():
    return redirect("https://docs.spoo.me"), 301


@docs.route("/docs/privacy-policy")
@docs.route("/legal/privacy-policy")
@docs.route("/privacy-policy")
@docs.route("/privacy")
@limiter.exempt
def serve_privacy_policy():
    return render_template("legal/privacy-policy.html", host_url=request.host_url)


@docs.route("/docs/terms-of-service")
@docs.route("/docs/tos")
@docs.route("/legal/terms-of-service")
@docs.route("/legal/tos")
@docs.route("/tos")
@docs.route("/terms-of-service")
@limiter.exempt
def serve_terms_of_service():
    return render_template("legal/terms-of-service.html", host_url=request.host_url)


@docs.route("/docs/<path:path>")
@limiter.exempt
def redirect_docs_wildcard(path):
    # Exclude specific paths that are handled by other routes
    excluded_paths = ["privacy-policy", "terms-of-service", "tos"]

    if path in excluded_paths:
        # This shouldn't happen since specific routes take precedence,
        # but handle it gracefully just in case
        return redirect(f"/docs/{path}"), 301

    return redirect(f"https://docs.spoo.me/{path}"), 301
