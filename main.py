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

app = Flask(__name__)

flask_secret = os.getenv("FLASK_SECRET_KEY")
if flask_secret:
    app.secret_key = flask_secret

# Enable credentials so refresh cookies can be sent cross-origin from frontend
CORS(app, supports_credentials=True)
limiter.init_app(app)

# Initialize OAuth
init_oauth_for_app(app)

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
    if request.path == "/contact":
        return render_template(
            "contact.html",
            error=f"ratelimit exceeded {e.description}",
            host_url=request.host_url,
        )
    if request.path == "/report":
        return render_template(
            "report.html",
            error=f"ratelimit exceeded {e.description}",
            host_url=request.host_url,
        )
    return make_response(jsonify(error=f"ratelimit exceeded {e.description}"), 429)


@atexit.register
def cleanup():
    try:
        client.close()
        print("[MongoDB] connection closed successfully")
    except Exception as e:
        print(f"Error closing MongoDB connection: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, use_reloader=True, debug=True)
