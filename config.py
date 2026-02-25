"""
Application configuration via pydantic-settings.

All settings are loaded from environment variables (and .env file).

Decision on secret key env var: kept as SECRET_KEY for the new app, but
FLASK_SECRET_KEY is also accepted as an alias for backward compatibility
(handled in AppSettings via model_validator).
"""

from __future__ import annotations

from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str
    db_name: str = "url-shortener"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Optional — self-hosters without Redis get degraded-but-functional behaviour
    redis_uri: Optional[str] = None
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

    # Sampling rates (0.0–1.0)
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


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    secret_key: str = ""
    flask_secret_key: str = ""  # backward-compat alias
    env: str = "development"
    app_url: str = "https://spoo.me"
    app_name: str = "spoo.me"

    # CORS — default matches current behaviour: all origins, credentials allowed
    cors_origins: list[str] = ["*"]

    # Request body size limit (bytes); 1 MB default
    max_content_length: int = 1_048_576

    # GeoIP database paths (configurable for self-hosters)
    geoip_country_db: str = "misc/GeoLite2-Country.mmdb"
    geoip_city_db: str = "misc/GeoLite2-City.mmdb"

    # External service URLs
    contact_webhook: str = ""
    url_report_webhook: str = ""
    hcaptcha_secret: str = ""

    # OpenAPI docs URL (None disables the docs UI in production)
    docs_url: Optional[str] = "/docs"

    # Sub-configs (composed via model_validator below)
    db: Optional[DatabaseSettings] = None
    redis: Optional[RedisSettings] = None
    jwt: Optional[JWTSettings] = None
    oauth: Optional[OAuthProviderSettings] = None
    email: Optional[EmailSettings] = None
    logging: Optional[LoggingSettings] = None
    sentry: Optional[SentrySettings] = None

    @model_validator(mode="after")
    def _populate_sub_configs_and_secret(self) -> "AppSettings":
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
