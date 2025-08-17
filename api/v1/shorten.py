from flask import request, jsonify, Response
from datetime import datetime, timezone
from bson import ObjectId

from blueprints.limiter import (
    limiter,
    dynamic_limit_for_request,
    rate_limit_key_for_request,
)
from utils.url_utils import (
	validate_url,
	validate_alias,
	validate_password,
	generate_short_code_v2,
	get_client_ip,
	validate_emoji_alias,
)
from utils.mongo_utils import (
	check_if_slug_exists,  # for backwards compatibility
	check_if_v2_alias_exists,
	validate_blocked_url,
	urls_v2_collection,
)
from utils.auth_utils import hash_password, resolve_owner_id_from_request

from . import api_v1
from typing import Optional


class ShortenRequestBuilder:
	def __init__(self, payload: dict):
		self.payload = payload
		self.error: Optional[tuple[Response, int]] = None
		self.now = datetime.now(timezone.utc)
		self.owner_id = resolve_owner_id_from_request()
		self.api_key_doc = getattr(request, "api_key", None)
		self.long_url: Optional[str] = None
		self.alias: Optional[str] = None
		self.password_hash = None
		self.block_bots: Optional[bool] = None
		self.max_clicks: Optional[int] = None
		self.expire_ts: Optional[int] = None
		self.private_stats: Optional[bool] = None

	def _fail(self, body: dict, status: int) -> "ShortenRequestBuilder":
		self.error = (jsonify(body), status)
		return self

	def parse_auth_scope(self, *, required_scopes: set[str]) -> "ShortenRequestBuilder":
		if self.api_key_doc is not None:
			scopes = set(self.api_key_doc.get("scopes", []))
			if "admin:all" not in scopes and "shorten:create" not in scopes:
				return self._fail(
					{"error": "api key lacks required scope: shorten:create"}, 403
				)
		return self

	def validate_long_url(self) -> "ShortenRequestBuilder":
		self.long_url = self.payload.get("long_url") or self.payload.get("url")
		if not self.long_url:
			return self._fail({"error": "long_url is required"}, 400)
		if not validate_url(self.long_url):
			return self._fail(
				{
					"error": "Invalid URL. URL must include a valid protocol and follow RFC patterns.",
					"field": "long_url",
				},
				400,
			)
		if not validate_blocked_url(self.long_url):
			return self._fail({"error": "Blocked URL"}, 403)
		return self

	def validate_alias(self) -> "ShortenRequestBuilder":
		custom_alias = self.payload.get("alias")
		if custom_alias:
			if not validate_alias(custom_alias):
				return self._fail({"error": "Invalid alias", "field": "alias"}, 400)
			alias = custom_alias[:16]
			if check_if_v2_alias_exists(alias) or check_if_slug_exists(alias):
				return self._fail({"error": "Alias already exists", "field": "alias"}, 409)
			self.alias = alias
		return self

	def validate_emoji(self) -> "ShortenRequestBuilder":
		emoji_alias = self.payload.get("emojies") or self.payload.get("emoji")
		if emoji_alias is None:
			return self
		if not validate_emoji_alias(emoji_alias):
			return self._fail({"error": "Invalid emoji alias", "field": "emojies"}, 400)
		self.alias = emoji_alias
		return self

	def validate_or_generate_alias(self) -> "ShortenRequestBuilder":
		# Try alias path if provided
		custom_alias = self.payload.get("alias")
		if custom_alias:
			return self.validate_alias()
		# Otherwise generate
		while True:
			candidate = generate_short_code_v2(7)
			if not check_if_v2_alias_exists(candidate):
				self.alias = candidate
				break
		return self

	def validate_password(self) -> "ShortenRequestBuilder":
		password = self.payload.get("password")
		if not password:
			self.password_hash = None
			return self
		if not validate_password(password):
			return self._fail(
				{
					"error": "Invalid password: must be >=8 chars, contain a letter, a number and one of '@' or '.' without consecutive specials.",
					"field": "password",
				},
				400,
			)
		self.password_hash = hash_password(password)
		return self

	def parse_block_bots(self) -> "ShortenRequestBuilder":
		self.block_bots = bool(self.payload.get("block_bots")) if "block_bots" in self.payload else None
		return self

	def parse_max_clicks(self) -> "ShortenRequestBuilder":
		max_clicks = self.payload.get("max_clicks")
		if max_clicks is None:
			self.max_clicks = None
			return self
		try:
			max_clicks = int(max_clicks)
			if max_clicks <= 0:
				raise ValueError()
		except Exception:
			return self._fail({"error": "max_clicks must be a positive integer"}, 400)
		self.max_clicks = max_clicks
		return self

	def parse_expire_after(self) -> "ShortenRequestBuilder":
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
		except Exception:
			return self._fail({"error": "expire_after must be ISO8601 or epoch seconds"}, 400)
		return self

	def parse_private_stats(self) -> "ShortenRequestBuilder":
		private_stats = self.payload.get("private_stats")
		if self.owner_id is not None and private_stats is None:
			self.private_stats = True
		elif self.owner_id is not None:
			self.private_stats = bool(private_stats)
		else:
			self.private_stats = None
		return self

	def build(self, *, collection) -> tuple[Response, int]:
		if self.error is not None:
			return self.error
		# Final safety checks
		if not self.long_url or not self.alias:
			return self._fail({"error": "missing required fields"}, 400).error  # type: ignore[return-value]

		# Ensure owner_id is stored as ObjectId for v2 docs
		owner_oid = None
		if self.owner_id is not None:
			try:
				owner_oid = ObjectId(self.owner_id) if not isinstance(self.owner_id, ObjectId) else self.owner_id
			except Exception:
				owner_oid = None

		doc = {
			"alias": self.alias,
			"owner_id": owner_oid,
			"created_at": self.now,
			"creation_ip": get_client_ip(),
			"long_url": self.long_url,
			"password": self.password_hash,
			"block_bots": self.block_bots if self.block_bots is not None else None,
			"max_clicks": self.max_clicks,
			"expire_after": self.expire_ts,
			"status": "ACTIVE",
			"private_stats": self.private_stats,
		}

		try:
			collection.insert_one(doc)
		except Exception:
			return jsonify({"error": "database error"}), 500

		body = {
			"alias": self.alias,
			"short_url": f"{request.host_url}{self.alias}",
			"long_url": self.long_url,
			"owner_id": str(self.owner_id) if self.owner_id else None,
			"created_at": int(self.now.timestamp()),
			"status": doc["status"],
			"private_stats": doc["private_stats"],
		}
		return jsonify(body), 201


@api_v1.route("/shorten", methods=["POST"])
@limiter.limit(
    lambda: dynamic_limit_for_request(
        authenticated="60 per minute; 5000 per day",
        anonymous="20 per minute; 1000 per day",
    ),
    key_func=rate_limit_key_for_request,
)
def shorten_v1() -> tuple[Response, int]:
	payload = request.get_json(silent=True) or {}

	builder = (
		ShortenRequestBuilder(payload)
		.parse_auth_scope(required_scopes={"shorten:create", "admin:all"})
		.validate_long_url()
		.validate_or_generate_alias()
		.validate_password()
		.parse_block_bots()
		.parse_max_clicks()
		.parse_expire_after()
		.parse_private_stats()
	)
	return builder.build(collection=urls_v2_collection)
