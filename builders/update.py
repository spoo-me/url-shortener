from flask import jsonify, Response
from bson import ObjectId
from typing import Optional

from utils.mongo_utils import urls_v2_collection
from utils.logger import get_logger
from cache import cache_query as cq

from .base import BaseUrlRequestBuilder

log = get_logger(__name__)


class UpdateUrlRequestBuilder(BaseUrlRequestBuilder):
    """Builder for updating existing URLs"""

    def __init__(self, payload: dict, url_id: str):
        super().__init__(payload)
        self.url_id = url_id
        self.existing_doc: Optional[dict] = None

    def load_and_validate_ownership(self) -> "UpdateUrlRequestBuilder":
        """Load existing URL and validate ownership"""
        if not self.url_id:
            return self._fail({"error": "URL ID is required"}, 400)

        try:
            url_oid = ObjectId(self.url_id)
        except Exception:
            return self._fail({"error": "Invalid URL ID format"}, 400)

        # Load the existing document
        try:
            self.existing_doc = urls_v2_collection.find_one({"_id": url_oid})
        except Exception:
            return self._fail({"error": "Database error"}, 500)

        if not self.existing_doc:
            return self._fail({"error": "URL not found"}, 404)

        # Validate ownership
        owner_oid = self._ensure_owner_object_id()
        if not owner_oid:
            return self._fail({"error": "Authentication required"}, 401)

        existing_owner = self.existing_doc.get("owner_id")
        if existing_owner != owner_oid:
            return self._fail({"error": "Access denied: You don't own this URL"}, 403)

        return self

    def validate_long_url_if_present(self) -> "UpdateUrlRequestBuilder":
        """Validate long_url only if it's being updated"""
        if "long_url" not in self.payload and "url" not in self.payload:
            return self

        # Use parent validation logic
        return self.validate_long_url()

    def validate_alias_custom(self) -> "UpdateUrlRequestBuilder":
        """Provides custom validation for alias updates"""
        if "alias" in self.payload:
            alias_value = self.payload.get("alias")
            # Treat same alias as no-op (idempotent update)
            if alias_value == self.existing_doc.get("alias"):
                return self

        # use parent validation logic for changed values
        return self.validate_alias()

    def parse_status_change(self) -> "UpdateUrlRequestBuilder":
        """Handle status changes (ACTIVE/INACTIVE)"""
        if "status" not in self.payload:
            return self

        status = self.payload.get("status")
        if status not in ["ACTIVE", "INACTIVE"]:
            return self._fail({"error": "Status must be ACTIVE or INACTIVE"}, 400)

        return self

    def build_update(self) -> tuple[Response, int]:
        """Execute the update operation"""
        if self.error is not None:
            return self.error

        # Build update operations from validated fields
        update_ops = {}

        # Check each field for changes
        if self.long_url and self.long_url != self.existing_doc.get("long_url"):
            update_ops["long_url"] = self.long_url

        if self.alias and self.alias != self.existing_doc.get("alias"):
            update_ops["alias"] = self.alias

        # Handle password (including removal)
        if "password" in self.payload:
            password = self.payload.get("password")
            if not password and self.existing_doc.get("password"):
                update_ops["password"] = None
            elif self.password_hash != self.existing_doc.get("password"):
                update_ops["password"] = self.password_hash

        # Handle max_clicks (including removal)
        if "max_clicks" in self.payload:
            max_clicks = self.payload.get("max_clicks")
            if (max_clicks is None or max_clicks == 0) and self.existing_doc.get(
                "max_clicks"
            ):
                update_ops["max_clicks"] = None
            elif self.max_clicks != self.existing_doc.get("max_clicks"):
                update_ops["max_clicks"] = self.max_clicks

        # Handle expire_after (including removal)
        if "expire_after" in self.payload:
            expire_after = self.payload.get("expire_after")
            if expire_after is None and self.existing_doc.get("expire_after"):
                update_ops["expire_after"] = None
            elif self.expire_ts != self.existing_doc.get("expire_after"):
                update_ops["expire_after"] = self.expire_ts

        # Handle block_bots (including removal)
        if "block_bots" in self.payload:
            block_bots = self.payload.get("block_bots")
            if block_bots is None and self.existing_doc.get("block_bots"):
                update_ops["block_bots"] = None
            elif self.block_bots != self.existing_doc.get("block_bots"):
                update_ops["block_bots"] = self.block_bots

        # Handle private_stats (including removal)
        if "private_stats" in self.payload:
            private_stats = self.payload.get("private_stats")
            if private_stats is None and self.existing_doc.get("private_stats"):
                update_ops["private_stats"] = None
            elif self.private_stats != self.existing_doc.get("private_stats"):
                update_ops["private_stats"] = self.private_stats

        # Handle status change
        if "status" in self.payload:
            status = self.payload.get("status")
            if status != self.existing_doc.get("status"):
                update_ops["status"] = status

        if not update_ops:
            return jsonify({"message": "No changes detected"}), 200

        # Add updated_at timestamp
        update_ops["updated_at"] = self.now

        try:
            url_oid = ObjectId(self.url_id)
            result = urls_v2_collection.update_one(
                {"_id": url_oid}, {"$set": update_ops}
            )

            if result.matched_count == 0:
                return jsonify({"error": "URL not found"}), 404

            log.info(
                "url_updated",
                url_id=self.url_id,
                alias=self.existing_doc.get("alias"),
                owner_id=str(self.owner_id) if self.owner_id else None,
                fields_changed=list(update_ops.keys()),
            )

            # invalidate the cache for the URL; for consistent cache state
            cq.invalidate_url_cache(short_code=self.existing_doc.get("alias"))

        except Exception as e:
            log.error(
                "url_update_failed",
                url_id=self.url_id,
                alias=self.existing_doc.get("alias") if self.existing_doc else None,
                error=str(e),
                error_type=type(e).__name__,
            )
            return jsonify({"error": "Database error"}), 500

        # Return updated document info
        updated_doc = {**self.existing_doc, **update_ops}

        body = {
            "id": self.url_id,
            "alias": updated_doc.get("alias"),
            "long_url": updated_doc.get("long_url"),
            "status": updated_doc.get("status"),
            "password_set": updated_doc.get("password") is not None,
            "max_clicks": updated_doc.get("max_clicks"),
            "expire_after": updated_doc.get("expire_after"),
            "block_bots": updated_doc.get("block_bots"),
            "private_stats": updated_doc.get("private_stats"),
            "updated_at": int(self.now.timestamp()),
        }

        return jsonify(body), 200
