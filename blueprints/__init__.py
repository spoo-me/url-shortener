# Blueprint imports for the URL shortener application

# Core authentication (email/password)
from .auth import auth

# OAuth authentication (Google, etc.)
from .oauth import oauth_bp, init_oauth_for_app

# Dashboard routes (settings, links, keys, statistics)
from .dashboard import dashboard_bp

# Other blueprints
from .api import api
from .contact import contact
from .docs import docs
from .limiter import limiter
from .seo import seo
from .stats import stats
from .url_shortener import url_shortener
from .redirector import url_redirector

__all__ = [
    "auth",
    "oauth_bp",
    "init_oauth_for_app",
    "dashboard_bp",
    "api",
    "contact",
    "docs",
    "limiter",
    "seo",
    "stats",
    "url_shortener",
    "url_redirector",
]
