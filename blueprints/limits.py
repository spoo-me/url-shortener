class Limits:
    """
    Single source of truth for all rate limit strings.
    All values use flask-limiter's "N per period" format.
    Semicolons combine multiple limits into one decorator.
    """

    # Global defaults (applied to every route unless overridden)
    DEFAULT_MINUTE = "10 per minute"
    DEFAULT_HOUR = "100 per hour"
    DEFAULT_DAY = "500 per day"

    # API v1 — authenticated vs anonymous tiers
    API_AUTHED = "60 per minute; 5000 per day"
    API_ANON = "20 per minute; 1000 per day"

    # Auth endpoints
    LOGIN = "5 per minute; 50 per day"
    SIGNUP = "5 per minute; 50 per day"
    LOGOUT = "60 per hour"
    TOKEN_REFRESH = "20 per minute"
    AUTH_READ = "60 per minute"  # /auth/me, /auth/verify page
    SET_PASSWORD = "5 per minute"
    RESEND_VERIFICATION = "3 per hour"
    EMAIL_VERIFY = "10 per hour"
    PASSWORD_RESET_REQUEST = "3 per hour"
    PASSWORD_RESET_CONFIRM = "5 per hour"

    # OAuth
    OAUTH_INIT = "10 per minute"
    OAUTH_CALLBACK = "20 per minute"
    OAUTH_LINK = "5 per minute"
    OAUTH_DISCONNECT = "5 per minute"

    # Dashboard
    DASHBOARD_READ = "60 per minute"
    DASHBOARD_WRITE = "30 per minute"
    DASHBOARD_SENSITIVE = "5 per minute"

    # API keys
    API_KEY_CREATE = "5 per hour"
    API_KEY_READ = "60 per minute"

    # Contact / report
    CONTACT_MINUTE = "3 per minute"
    CONTACT_HOUR = "10 per hour"
    CONTACT_DAY = "20 per day"

    # URL shortener (legacy endpoint)
    SHORTEN_LEGACY = "100 per minute"

    # Legacy stats / export pages (unauthenticated; mirrors the anonymous API tiers)
    STATS_LEGACY_PAGE = "20 per minute; 1000 per day"
    STATS_LEGACY_EXPORT = "10 per minute; 200 per day"

    # Password-protected URL check
    PASSWORD_CHECK = "10 per minute; 30 per hour"
