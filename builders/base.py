from flask import request, jsonify, Response
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional

from utils.url_utils import (
    validate_url,
    validate_alias,
    validate_password,
)
from utils.mongo_utils import (
    check_if_v2_alias_exists,
    check_if_slug_exists,
    validate_blocked_url,
)
from utils.auth_utils import hash_password, resolve_owner_id_from_request
from utils.logger import get_logger

log = get_logger(__name__)


class BaseUrlRequestBuilder:
    """Base class for URL request operations (create, update)"""

    def __init__(self, payload: dict):
        self.payload = payload
        self.error: Optional[tuple[Response, int]] = None
        self.now = datetime.now(timezone.utc)
        self.owner_id = resolve_owner_id_from_request()
        self.api_key_doc = getattr(request, "api_key", None)

        # Common fields
        self.long_url: Optional[str] = None
        self.alias: Optional[str] = None
        self.password_hash = None
        self.block_bots: Optional[bool] = None
        self.max_clicks: Optional[int] = None
        self.expire_ts: Optional[int] = None
        self.private_stats: Optional[bool] = None

    def _fail(self, body: dict, status: int) -> "BaseUrlRequestBuilder":
        self.error = (jsonify(body), status)
        return self

    def parse_auth_scope(self, *, required_scopes: set[str]) -> "BaseUrlRequestBuilder":
        if self.api_key_doc is not None:
            scopes = set(self.api_key_doc.get("scopes", []))
            if "admin:all" not in scopes and not any(
                scope in scopes for scope in required_scopes
            ):
                scope_list = ", ".join(required_scopes)
                log.warning(
                    "url_request_access_denied",
                    reason="missing_scope",
                    required_scopes=list(required_scopes),
                    api_key_scopes=list(scopes),
                )
                return self._fail(
                    {"error": f"api key lacks required scope: {scope_list}"}, 403
                )
        return self

    def validate_long_url(self) -> "BaseUrlRequestBuilder":
        self.long_url = self.payload.get("long_url") or self.payload.get("url")
        if not self.long_url:
            return self._fail({"error": "long_url is required"}, 400)
        if not validate_url(self.long_url):
            log.info(
                "url_validation_failed",
                reason="invalid_url_format",
                url_length=len(self.long_url),
                url_preview=self.long_url[:100],  # Truncate for logging
            )
            return self._fail(
                {
                    "error": "Invalid URL. URL must include a valid protocol and follow RFC patterns.",
                    "field": "long_url",
                },
                400,
            )
        if not validate_blocked_url(self.long_url):
            log.warning(
                "blocked_url_attempt",
                url=self.long_url[:100],  # Truncate for logging
                owner_id=str(self.owner_id) if self.owner_id else None,
            )
            return self._fail({"error": "Blocked URL"}, 403)
        return self

    def validate_alias(self) -> "BaseUrlRequestBuilder":
        custom_alias = self.payload.get("alias")
        if custom_alias:
            if not validate_alias(custom_alias):
                log.info(
                    "alias_validation_failed",
                    reason="invalid_format",
                    alias=custom_alias[:50],  # Truncate for logging
                    alias_length=len(custom_alias),
                )
                return self._fail({"error": "Invalid alias", "field": "alias"}, 400)
            alias = custom_alias[:16]
            if check_if_v2_alias_exists(alias) or check_if_slug_exists(alias):
                log.info(
                    "alias_conflict",
                    alias=alias,
                    owner_id=str(self.owner_id) if self.owner_id else None,
                )
                return self._fail(
                    {"error": "Alias already exists", "field": "alias"}, 409
                )
            self.alias = alias
        return self

    def validate_password(self) -> "BaseUrlRequestBuilder":
        password = self.payload.get("password")
        if not password:
            self.password_hash = None
            return self
        if not validate_password(password):
            log.info("password_validation_failed", password_length=len(password))
            return self._fail(
                {
                    "error": "Invalid password: must be >=8 chars, contain a letter, a number and one of '@' or '.' without consecutive specials.",
                    "field": "password",
                },
                400,
            )
        self.password_hash = hash_password(password)
        return self

    def parse_block_bots(self) -> "BaseUrlRequestBuilder":
        self.block_bots = (
            bool(self.payload.get("block_bots"))
            if "block_bots" in self.payload
            else None
        )
        return self

    def parse_max_clicks(self) -> "BaseUrlRequestBuilder":
        max_clicks = self.payload.get("max_clicks")
        if max_clicks is None:
            self.max_clicks = None
            return self
        try:
            max_clicks = int(max_clicks)
            if max_clicks <= 0:
                raise ValueError()
        except Exception as e:
            log.info(
                "max_clicks_validation_failed",
                max_clicks_raw=self.payload.get("max_clicks"),
                error=str(e),
            )
            return self._fail({"error": "max_clicks must be a positive integer"}, 400)
        self.max_clicks = max_clicks
        return self

    def parse_expire_after(self) -> "BaseUrlRequestBuilder":
        expire_after = self.payload.get("expire_after")
        if expire_after is None:
            self.expire_ts = None
            return self
        try:
            if isinstance(expire_after, (int, float)):
                self.expire_ts = int(expire_after)
            else:
                dt = datetime.fromisoformat(str(expire_after))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                self.expire_ts = int(dt.timestamp())
        except Exception as e:
            log.info(
                "expire_after_validation_failed",
                expire_after_raw=str(self.payload.get("expire_after"))[:50],
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._fail(
                {"error": "expire_after must be ISO8601 or epoch seconds"}, 400
            )
        return self

    def parse_private_stats(self) -> "BaseUrlRequestBuilder":
        private_stats = self.payload.get("private_stats")
        if self.owner_id is not None and private_stats is None:
            self.private_stats = True
        elif self.owner_id is not None:
            self.private_stats = bool(private_stats)
        else:
            self.private_stats = None
        return self

    def _ensure_owner_object_id(self) -> Optional[ObjectId]:
        """Convert owner_id to ObjectId if needed"""
        if self.owner_id is None:
            return None
        try:
            return (
                ObjectId(self.owner_id)
                if not isinstance(self.owner_id, ObjectId)
                else self.owner_id
            )
        except Exception:
            return None
