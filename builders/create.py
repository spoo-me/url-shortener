from flask import request, jsonify, Response

from utils.url_utils import (
    generate_short_code_v2,
    get_client_ip,
)
from utils.mongo_utils import check_if_v2_alias_exists

from .base import BaseUrlRequestBuilder


class ShortenRequestBuilder(BaseUrlRequestBuilder):
    """Builder for creating new shortened URLs"""

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

    def build(self, *, collection) -> tuple[Response, int]:
        if self.error is not None:
            return self.error
        # Final safety checks
        if not self.long_url or not self.alias:
            return self._fail({"error": "missing required fields"}, 400).error  # type: ignore[return-value]

        # Ensure owner_id is stored as ObjectId for v2 docs
        owner_oid = self._ensure_owner_object_id()

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
