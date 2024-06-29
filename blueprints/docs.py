from flask import Blueprint
from utils import *
from .limiter import limiter
import os

docs = Blueprint("docs", __name__)


@docs.route("/docs")
@limiter.exempt
def serve_docs_index():
    return render_template("docs/index.html", host_url=request.host_url)

@docs.route("/docs/<path:file_path>")
@limiter.exempt
def serve_docs(file_path):
    try:
        if file_path == "":
            return render_template("docs/index.html", host_url=request.host_url)
        if not os.path.exists(f"templates/docs/{file_path}.html"):
            raise FileNotFoundError
        return render_template(f"docs/{file_path}.html", host_url=request.host_url)
    except:
        return (
            render_template(
                "error.html",
                error_code="404",
                error_message="URL NOT FOUND",
                host_url=request.host_url,
            ),
            404,
        )

@docs.route("/legal/privacy-policy")
@limiter.exempt
def serve_privacy_policy():
    return render_template("docs/privacy-policy.html", host_url=request.host_url)

@docs.route("/legal/terms-of-service")
@docs.route("/legal/tos")
@limiter.exempt
def serve_terms_of_service():
    return render_template("docs/terms-of-service.html", host_url=request.host_url)
