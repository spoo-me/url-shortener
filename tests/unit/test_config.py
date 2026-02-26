"""Unit tests for AppSettings and sub-configs."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from config import (
    AppSettings,
    DatabaseSettings,
    JWTSettings,
    RedisSettings,
)


class TestDatabaseSettings:
    def test_loads_mongodb_uri(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        s = DatabaseSettings()
        assert s.mongodb_uri == "mongodb://localhost:27017/"

    def test_default_db_name(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        s = DatabaseSettings()
        assert s.db_name == "url-shortener"

    def test_missing_mongodb_uri_raises(self, monkeypatch):
        monkeypatch.delenv("MONGODB_URI", raising=False)
        with pytest.raises((PydanticValidationError, Exception)):
            DatabaseSettings()


class TestRedisSettings:
    def test_redis_uri_optional(self, monkeypatch):
        monkeypatch.delenv("REDIS_URI", raising=False)
        s = RedisSettings()
        assert s.redis_uri is None

    def test_redis_uri_loaded(self, monkeypatch):
        monkeypatch.setenv("REDIS_URI", "redis://localhost:6379")
        s = RedisSettings()
        assert s.redis_uri == "redis://localhost:6379"

    def test_default_ttl(self, monkeypatch):
        monkeypatch.delenv("REDIS_TTL_SECONDS", raising=False)
        s = RedisSettings()
        assert s.redis_ttl_seconds == 3600


class TestJWTSettings:
    def test_defaults(self, monkeypatch):
        for var in (
            "JWT_ISSUER",
            "JWT_AUDIENCE",
            "ACCESS_TOKEN_TTL_SECONDS",
            "REFRESH_TOKEN_TTL_SECONDS",
            "COOKIE_SECURE",
            "JWT_PRIVATE_KEY",
            "JWT_PUBLIC_KEY",
            "JWT_SECRET",
        ):
            monkeypatch.delenv(var, raising=False)
        s = JWTSettings()
        assert s.jwt_issuer == "spoo.me"
        assert s.jwt_audience == "spoo.me.api"
        assert s.access_token_ttl_seconds == 900
        assert s.refresh_token_ttl_seconds == 2592000

    def test_use_rs256_false_when_keys_absent(self, monkeypatch):
        monkeypatch.delenv("JWT_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("JWT_PUBLIC_KEY", raising=False)
        s = JWTSettings()
        assert s.use_rs256 is False

    def test_use_rs256_true_when_keys_present(self, monkeypatch):
        monkeypatch.setenv("JWT_PRIVATE_KEY", "private")
        monkeypatch.setenv("JWT_PUBLIC_KEY", "public")
        s = JWTSettings()
        assert s.use_rs256 is True


class TestAppSettings:
    def test_flask_secret_key_fallback(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        monkeypatch.setenv("FLASK_SECRET_KEY", "flask-secret")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        s = AppSettings()
        assert s.secret_key == "flask-secret"

    def test_secret_key_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        monkeypatch.setenv("SECRET_KEY", "new-secret")
        monkeypatch.setenv("FLASK_SECRET_KEY", "old-secret")
        s = AppSettings()
        assert s.secret_key == "new-secret"

    def test_sub_configs_populated(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        s = AppSettings()
        assert s.db is not None
        assert s.redis is not None
        assert s.jwt is not None
        assert s.oauth is not None
        assert s.email is not None
        assert s.logging is not None
        assert s.sentry is not None

    def test_is_production_false_by_default(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        s = AppSettings()
        assert s.is_production is False

    def test_is_production_true(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        monkeypatch.setenv("ENV", "production")
        s = AppSettings()
        assert s.is_production is True

    def test_cors_origins_default(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
        s = AppSettings()
        assert s.cors_origins == ["*"]
