"""
Application configuration via pydantic-settings.

All settings are loaded from environment variables (and .env file).

Decision on secret key env var: kept as SECRET_KEY for the new app, but
FLASK_SECRET_KEY is also accepted as an alias for backward compatibility
(handled in AppSettings via model_validator).
"""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str
    db_name: str = "url-shortener"
    max_pool_size: int = 200
    min_pool_size: int = 10


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Optional — self-hosters without Redis get degraded-but-functional behaviour
    redis_uri: str | None = None
    redis_ttl_seconds: int = 3600


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_issuer: str = "spoo.me"
    jwt_audience: str = "spoo.me.api"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2592000
    cookie_secure: bool = True

    # RS256 keys (preferred)
    jwt_private_key: str = ""
    jwt_public_key: str = ""

    # HS256 fallback (used when RS256 keys are absent)
    jwt_secret: str = ""

    @property
    def use_rs256(self) -> bool:
        return bool(self.jwt_private_key and self.jwt_public_key)


class OAuthProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""

    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    github_oauth_redirect_uri: str = ""

    discord_oauth_client_id: str = ""
    discord_oauth_client_secret: str = ""
    discord_oauth_redirect_uri: str = ""


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    zepto_api_token: str = ""
    zepto_from_email: str = "noreply@spoo.me"
    zepto_from_name: str = "spoo.me"


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    log_format: str = "console"  # "json" in production

    # Sampling rates (0.0-1.0)
    sample_rate_redirect: float = 0.05
    sample_rate_stats: float = 0.20
    sample_rate_cache: float = 0.01
    sample_rate_export: float = 0.80


class SentrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sentry_dsn: str = ""
    sentry_send_pii: bool = False
    sentry_traces_sample_rate: float = 0.1
    sentry_profile_sample_rate: float = 0.05

    @property
    def client_key(self) -> str:
        """Extract the public key from the DSN for the frontend loader script."""
        if not self.sentry_dsn:
            return ""
        try:
            return urlparse(self.sentry_dsn).username or ""
        except Exception:
            return ""


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    secret_key: str = ""
    flask_secret_key: str = ""  # backward-compat alias
    env: str = "development"
    app_url: str = "https://spoo.me"
    app_name: str = "spoo.me"

    # CORS — public API routes allow all origins (no credentials).
    # Private routes (auth, oauth, dashboard) require explicit origin allowlist.
    cors_origins: list[str] = ["*"]  # deprecated — kept for backward compat
    cors_private_origins: list[str] = []

    # Request body size limit (bytes); 1 MB default
    max_content_length: int = 1_048_576

    # GeoIP database paths (configurable for self-hosters)
    geoip_country_db: str = "misc/GeoLite2-Country.mmdb"
    geoip_city_db: str = "misc/GeoLite2-City.mmdb"

    # GitHub repository (owner/repo) — used for star count + outbound links
    github_repo: str = "spoo-me/spoo"

    # Analytics & tracking (leave empty to disable)
    clarity_id: str = ""

    # External service URLs
    contact_webhook: str = ""
    url_report_webhook: str = ""
    hcaptcha_secret: str = ""
    hcaptcha_sitekey: str = ""

    # Service limits (overridable by self-hosters via env vars)
    max_active_api_keys: int = 20
    max_date_range_days: int = 90
    http_client_timeout: float = 5.0

    # Validator constraints (overridable by self-hosters via env vars)
    blocked_url_regex_timeout: float = 0.2
    max_emoji_alias_length: int = 15
    url_password_min_length: int = 8
    account_password_min_length: int = 8
    account_password_max_length: int = 128

    # ── Field validators for safety-critical config ────────────────────

    @field_validator(
        "max_active_api_keys", "max_date_range_days", "max_emoji_alias_length"
    )
    @classmethod
    def _must_be_positive_int(cls, v: int, info) -> int:
        if v < 1:
            raise ValueError(f"{info.field_name} must be >= 1, got {v}")
        return v

    @field_validator("http_client_timeout", "blocked_url_regex_timeout")
    @classmethod
    def _must_be_positive_float(cls, v: float, info) -> float:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0, got {v}")
        return v

    @field_validator("url_password_min_length", "account_password_min_length")
    @classmethod
    def _password_min_length_sane(cls, v: int, info) -> int:
        if v < 1:
            raise ValueError(f"{info.field_name} must be >= 1, got {v}")
        return v

    @field_validator("account_password_max_length")
    @classmethod
    def _password_max_length_sane(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"account_password_max_length must be >= 1, got {v}")
        return v

    # Sub-configs (composed via model_validator below)
    db: DatabaseSettings | None = None
    redis: RedisSettings | None = None
    jwt: JWTSettings | None = None
    oauth: OAuthProviderSettings | None = None
    email: EmailSettings | None = None
    logging: LoggingSettings | None = None
    sentry: SentrySettings | None = None

    @model_validator(mode="after")
    def _populate_sub_configs_and_secret(self) -> AppSettings:
        # Cross-field validation
        if self.account_password_max_length < self.account_password_min_length:
            raise ValueError(
                f"account_password_max_length ({self.account_password_max_length}) "
                f"must be >= account_password_min_length ({self.account_password_min_length})"
            )

        # Accept FLASK_SECRET_KEY as a fallback for backward compatibility
        if not self.secret_key and self.flask_secret_key:
            self.secret_key = self.flask_secret_key

        # Populate sub-configs from the same env/dotenv source
        if self.db is None:
            self.db = DatabaseSettings()
        if self.redis is None:
            self.redis = RedisSettings()
        if self.jwt is None:
            self.jwt = JWTSettings()
        if self.oauth is None:
            self.oauth = OAuthProviderSettings()
        if self.email is None:
            self.email = EmailSettings()
        if self.logging is None:
            self.logging = LoggingSettings()
        if self.sentry is None:
            self.sentry = SentrySettings()

        return self

    @property
    def is_production(self) -> bool:
        return self.env == "production"
