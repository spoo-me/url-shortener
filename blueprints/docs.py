from flask import Blueprint
from utils import *
from .limiter import limiter

docs = Blueprint("docs", __name__)


@docs.route("/docs/<file_name>")
@limiter.exempt
def serve_docs(file_name):
    try:
        ext = file_name.split(".")[1]
        if ext in ["html"]:
            return render_template(f"docs/{file_name}", host_url=request.host_url)
        else:
            return send_file(f"docs/{file_name}")
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
