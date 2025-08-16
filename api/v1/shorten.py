from flask import request, jsonify, Response
from datetime import datetime, timezone
from bson import ObjectId

from blueprints.limiter import limiter
from utils.url_utils import (
    validate_url,
    validate_alias,
    validate_password,
    generate_short_code_v2,
    get_client_ip,
)
from utils.mongo_utils import (
    insert_url_v2,
    check_if_slug_exists,  # for backwards compatibility
    check_if_v2_alias_exists,
    validate_blocked_url,
)
from utils.auth_utils import verify_access_jwt, hash_password
from utils.mongo_utils import find_api_key_by_hash
import hashlib

from . import api_v1

from typing import Optional


def _resolve_owner_id_from_request() -> Optional[ObjectId]:
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        # API key path: Authorization: Bearer spoo_<key>
        if token.startswith("spoo_"):
            raw = token[len("spoo_") :]
            token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            key_doc = find_api_key_by_hash(token_hash)
            # Validate key
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            if (
                key_doc
                and not key_doc.get("revoked", False)
                and (not key_doc.get("expires_at") or key_doc["expires_at"] > now)
            ):
                # Attach scopes for downstream checks
                request.api_key = key_doc  # type: ignore[attr-defined]
                user_id = key_doc.get("user_id")
                try:
                    return ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
                except Exception:
                    return None
    if not token:
        token = request.cookies.get("access_token")
    if token:
        try:
            claims = verify_access_jwt(token)
            user_id = claims.get("sub")
            return ObjectId(user_id)
        except Exception:
            pass
    # TODO: API key ownership resolution
    return None


def _choose_rate_limit() -> str:
    if _resolve_owner_id_from_request() is not None:
        return "60 per minute; 5000 per day"
    return "20 per minute; 1000 per day"


def _rate_limit_key() -> str:
    owner_id = _resolve_owner_id_from_request()
    if owner_id is not None:
        return f"user:{str(owner_id)}"
    # API key already parsed in Authorization header; bucket by token hash prefix if present
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token.startswith("spoo_"):
            return f"apikey:{token[:20]}"
    return get_client_ip()


@api_v1.route("/shorten", methods=["POST"])
@limiter.limit(lambda: _choose_rate_limit(), key_func=_rate_limit_key)
def shorten_v1() -> tuple[Response, int]:
    payload = request.get_json(silent=True) or {}

    long_url = payload.get("long_url") or payload.get("url")
    custom_alias = payload.get("alias")
    password = payload.get("password")
    block_bots = bool(payload.get("block_bots")) if "block_bots" in payload else None
    max_clicks = payload.get("max_clicks")
    expire_after = payload.get("expire_after")
    private_stats = payload.get("private_stats")

    if not long_url:
        return jsonify({"error": "long_url is required"}), 400
    if not validate_url(long_url):
        return (
            jsonify(
                {
                    "error": "Invalid URL. URL must include a valid protocol and follow RFC patterns.",
                    "field": "long_url",
                }
            ),
            400,
        )
    if not validate_blocked_url(long_url):
        return jsonify({"error": "Blocked URL"}), 403

    alias: str
    if custom_alias:
        if not validate_alias(custom_alias):
            return jsonify({"error": "Invalid alias", "field": "alias"}), 400
        alias = custom_alias[:16]
        if check_if_v2_alias_exists(alias):
            return jsonify({"error": "Alias already exists", "field": "alias"}), 409
        # TODO: Remove this check after a few months
        # this is for backwards compatibility
        if check_if_slug_exists(alias):
            return jsonify({"error": "Alias already exists", "field": "alias"}), 409
    else:
        while True:
            alias = generate_short_code_v2(7)
            if not check_if_v2_alias_exists(alias):
                break

    password_hash = None
    if password:
        if not validate_password(password):
            return (
                jsonify(
                    {
                        "error": "Invalid password: must be >=8 chars, contain a letter, a number and one of '@' or '.' without consecutive specials.",
                        "field": "password",
                    }
                ),
                400,
            )
        password_hash = hash_password(password)

    if max_clicks is not None:
        try:
            max_clicks = int(max_clicks)
            if max_clicks <= 0:
                raise ValueError()
        except Exception:
            return jsonify({"error": "max_clicks must be a positive integer"}), 400

    expire_ts = None
    if expire_after is not None:
        try:
            if isinstance(expire_after, (int, float)):
                expire_ts = int(expire_after)
            else:
                dt = datetime.fromisoformat(str(expire_after))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                expire_ts = int(dt.timestamp())
        except Exception:
            return jsonify(
                {"error": "expire_after must be ISO8601 or epoch seconds"}
            ), 400

    owner_id = _resolve_owner_id_from_request()
    # If API key used, enforce scope
    api_key_doc = getattr(request, "api_key", None)
    if api_key_doc is not None:
        scopes = set(api_key_doc.get("scopes", []))
        if "admin:all" not in scopes and "shorten:create" not in scopes:
            return jsonify({"error": "api key lacks required scope: shorten:create"}), 403
    now = datetime.now(timezone.utc)

    # Ensure owner_id is stored as ObjectId for v2 docs
    owner_oid = None
    if owner_id is not None:
        try:
            owner_oid = ObjectId(owner_id) if not isinstance(owner_id, ObjectId) else owner_id
        except Exception:
            owner_oid = None

    doc = {
        "alias": alias,
        "owner_id": owner_oid,
        "created_at": now,
        "creation_ip": get_client_ip(),
        "long_url": long_url,
        "password": password_hash,
        "block_bots": block_bots if block_bots is not None else None,
        "max_clicks": max_clicks,
        "expire_after": expire_ts,
        "status": "ACTIVE",
        "private_stats": (
            True
            if (owner_id is not None and private_stats is None)
            else (bool(private_stats) if owner_id is not None else None)
        ),
    }

    insert_url_v2(doc)

    body = {
        "alias": alias,
        "short_url": f"{request.host_url}{alias}",
        "long_url": long_url,
        "owner_id": str(owner_id) if owner_id else None,
        "created_at": int(now.timestamp()),
        "status": doc["status"],
        "private_stats": doc["private_stats"],
    }

    return jsonify(body), 201
