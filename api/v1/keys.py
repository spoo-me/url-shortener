from flask import request, jsonify, g
from datetime import datetime, timezone
import secrets
import hashlib
from typing import Optional

from utils.auth_utils import requires_auth
from bson import ObjectId
from utils.mongo_utils import (
    insert_api_key,
    list_api_keys_by_user,
    revoke_api_key_by_id,
)

from . import api_v1


ALLOWED_SCOPES = {
    "shorten:create",
    "urls:manage",
    "stats:read",
    "admin:all",
}


def _parse_expires_at(value: Optional[str | int | float]):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


@api_v1.route("/keys", methods=["POST"])
@requires_auth
def create_api_key():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip() or None
    scopes = body.get("scopes") or []
    expires_at_raw = body.get("expires_at")

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not isinstance(scopes, list) or not scopes:
        return jsonify({"error": "scopes must be a non-empty array"}), 400
    if any(scope not in ALLOWED_SCOPES for scope in scopes):
        return jsonify({"error": "invalid scope requested"}), 400

    expires_at = _parse_expires_at(expires_at_raw)
    if expires_at_raw is not None and expires_at is None:
        return jsonify({"error": "expires_at must be ISO8601 or epoch seconds"}), 400
    if expires_at and expires_at <= datetime.now(timezone.utc):
        return jsonify({"error": "expires_at must be in the future"}), 400

    # Generate key
    raw = secrets.token_urlsafe(32)
    token_prefix = raw[:8]
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    user_oid = ObjectId(g.user_id) if not isinstance(g.user_id, ObjectId) else g.user_id
    doc = {
        "user_id": user_oid,
        "token_prefix": token_prefix,
        "token_hash": token_hash,
        "name": name,
        "description": description,
        "scopes": scopes,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
        "revoked": False,
    }

    key_id = insert_api_key(doc)
    if not key_id:
        return jsonify({"error": "failed to create api key"}), 500

    return (
        jsonify(
            {
                "id": str(key_id),
                "name": name,
                "description": description,
                "scopes": scopes,
                "created_at": int(doc["created_at"].timestamp()),
                "expires_at": int(expires_at.timestamp()) if expires_at else None,
                "revoked": False,
                "token_prefix": token_prefix,
                "token": f"spoo_{raw}",
            }
        ),
        201,
    )


@api_v1.route("/keys", methods=["GET"])
@requires_auth
def list_api_keys():
    keys = list_api_keys_by_user(g.user_id)
    result = []
    for k in keys:
        result.append(
            {
                "id": str(k["_id"]),
                "name": k.get("name"),
                "description": k.get("description"),
                "scopes": k.get("scopes", []),
                "created_at": int(k.get("created_at").timestamp()) if k.get("created_at") else None,
                "expires_at": int(k.get("expires_at").timestamp()) if k.get("expires_at") else None,
                "revoked": bool(k.get("revoked", False)),
                "token_prefix": k.get("token_prefix"),
            }
        )
    return jsonify({"keys": result})


@api_v1.route("/keys/<key_id>", methods=["DELETE"])
@requires_auth
def delete_api_key(key_id):
    hard = (request.args.get("hard") or "false").lower() == "true"
    ok = revoke_api_key_by_id(g.user_id, key_id, hard_delete=hard)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})


