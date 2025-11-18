from flask import Blueprint, render_template, request, redirect
from .limiter import limiter

api = Blueprint("api", __name__)


@api.route("/api", methods=["GET"])
@limiter.exempt
def api_route():
    if request.args.get("old") == "1":
        return render_template(
            "api.html",
            host_url=request.host_url,
            self_promo=True,
            self_promo_uri="https://docs.spoo.me",
            self_promo_text="We have moved and revamped the docs to https://docs.spoo.me",
        )
    else:
        return redirect("https://docs.spoo.me/introduction"), 301
