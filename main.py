import atexit
import os

from flask import (
    Flask,
    jsonify,
    make_response,
    render_template,
    request,
)
from flask_cors import CORS
import sentry_sdk

from blueprints.api import api
from blueprints.contact import contact
from blueprints.docs import docs
from blueprints.limiter import limiter
from blueprints.seo import seo
from blueprints.stats import stats
from blueprints.url_shortener import url_shortener
from blueprints.redirector import url_redirector
from blueprints.auth import auth
from blueprints.oauth import oauth_bp, init_oauth_for_app
from blueprints.dashboard import dashboard_bp
from api.v1 import api_v1
from utils.mongo_utils import client, ensure_indexes
from utils.log_context import setup_logging_middleware
from utils.logging_config import setup_logging
from utils.logger import get_logger, hash_ip

from utils.url_utils import get_client_ip
from utils.auth_utils import resolve_owner_id_from_request

setup_logging()
app = Flask(__name__)
log = get_logger(__name__)

flask_secret = os.getenv("FLASK_SECRET_KEY")
if not flask_secret:
    raise RuntimeError(
        "FLASK_SECRET_KEY is not set. Refusing to start with unsigned session cookies."
    )
app.secret_key = flask_secret

# Enable credentials so refresh cookies can be sent cross-origin from frontend
CORS(app, supports_credentials=True)
limiter.init_app(app)

# Initialize OAuth
init_oauth_for_app(app)

# Setup logging middleware (after OAuth, before routes)
setup_logging_middleware(app)

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        send_default_pii=os.getenv("SENTRY_SEND_PII", "false").lower() == "true",
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        enable_logs=True,
        profile_session_sample_rate=float(
            os.getenv("SENTRY_PROFILE_SAMPLE_RATE", "0.05")
        ),
        profile_lifecycle="trace",
    )
    log.info(
        "sentry_initialized",
        pii=os.getenv("SENTRY_SEND_PII", "false").lower() == "true",
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profile_sample_rate=float(os.getenv("SENTRY_PROFILE_SAMPLE_RATE", "0.05")),
    )

ensure_indexes()

app.register_blueprint(url_shortener)
app.register_blueprint(url_redirector)
app.register_blueprint(docs)
app.register_blueprint(seo)
app.register_blueprint(contact)
app.register_blueprint(api)
app.register_blueprint(stats)
app.register_blueprint(auth)
app.register_blueprint(oauth_bp, url_prefix="/oauth")
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
app.register_blueprint(api_v1)


@app.errorhandler(404)
def page_not_found(error):
    return (
        render_template(
            "error.html",
            error_code="404",
            error_message="URL NOT FOUND!",
            host_url=request.host_url,
        ),
        404,
    )


@app.errorhandler(429)
def ratelimit_handler(e):
    # Log rate limit hit
    owner_id = resolve_owner_id_from_request()
    log.warning(
        "rate_limit_hit",
        path=request.path,
        method=request.method,
        limit=e.description,
        ip_hash=hash_ip(get_client_ip()),
        user_id=str(owner_id) if owner_id else None,
    )

    # Prepare error message with signup nudge for anonymous users
    is_anonymous = owner_id is None
    error_message = f"ratelimit exceeded {e.description}"

    if is_anonymous:
        error_message += (
            ". Sign up for free to get 5x higher rate limits (5000 requests/day)!"
        )

    if request.path == "/contact":
        return render_template(
            "contact.html",
            error=error_message,
            host_url=request.host_url,
        )
    if request.path == "/report":
        return render_template(
            "report.html",
            error=error_message,
            host_url=request.host_url,
        )
    return make_response(jsonify(error=error_message), 429)


@atexit.register
def cleanup():
    try:
        client.close()
        log.info("mongodb_connection_closed")
    except Exception as e:
        log.error(
            "mongodb_connection_close_failed", error=str(e), error_type=type(e).__name__
        )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        use_reloader=os.getenv("ENV") != "production",
        debug=os.getenv("ENV") != "production",
    )
