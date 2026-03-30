"""
URL resolution, creation, update, deletion, and listing service.

Extracts business logic from:
  - blueprints/redirector.py  (resolve + dispatch heuristic)
  - builders/create.py        (create)
  - builders/update.py        (update)
  - builders/query.py         (list_by_owner)

Dispatch heuristic (get_url_by_length_and_type) is preserved exactly:
  emoji alias  → emojis collection, schema "emoji"
  7 chars      → urlsV2 first, urls fallback
  6 chars      → urls first, urlsV2 fallback
  other        → urlsV2 first, urls fallback
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from bson import ObjectId

from errors import (
    AppError,
    BlockedUrlError,
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    ValidationError,
)
from infrastructure.cache.url_cache import UrlCache, UrlCacheData
from repositories.blocked_url_repository import BlockedUrlRepository
from repositories.legacy.emoji_url_repository import EmojiUrlRepository
from repositories.legacy.legacy_url_repository import LegacyUrlRepository
from repositories.url_repository import UrlRepository
from schemas.dto.requests.url import CreateUrlRequest, ListUrlsQuery, UpdateUrlRequest
from schemas.models.base import ANONYMOUS_OWNER_ID
from schemas.models.url import (
    EmojiUrlDoc,
    LegacyUrlDoc,
    SchemaVersion,
    UrlStatus,
    UrlV2Doc,
)
from shared.crypto import hash_password
from shared.datetime_utils import parse_datetime
from shared.generators import generate_short_code_v2
from shared.logging import get_logger, should_sample
from shared.validators import (
    validate_alias,
    validate_blocked_url,
    validate_emoji_alias,
    validate_url,
)

log = get_logger(__name__)


class UrlService:
    def __init__(
        self,
        url_repo: UrlRepository,
        legacy_repo: LegacyUrlRepository,
        emoji_repo: EmojiUrlRepository,
        blocked_url_repo: BlockedUrlRepository,
        url_cache: UrlCache,
        blocked_self_domains: list[str],
    ) -> None:
        self._url_repo = url_repo
        self._legacy_repo = legacy_repo
        self._emoji_repo = emoji_repo
        self._blocked_url_repo = blocked_url_repo
        self._url_cache = url_cache
        self._blocked_self_domains = blocked_self_domains

    # ── Public API ────────────────────────────────────────────────────────────

    async def resolve(self, short_code: str) -> tuple[UrlCacheData, SchemaVersion]:
        """
        Resolve a short code to UrlCacheData and schema version.

        Returns (UrlCacheData, schema_version) where schema_version is
        a SchemaVersion enum member (V2, V1, or EMOJI).

        Raises:
            NotFoundError:   URL not found in any collection.
            BlockedUrlError: URL status is BLOCKED (v2 only).
            GoneError:       URL status is EXPIRED or INACTIVE (v2 only).
        """
        # 1. Cache hit
        cached = await self._url_cache.get(short_code)
        if cached is not None:
            schema = cached.schema_version
            if schema == SchemaVersion.V2 and cached.url_status in (
                UrlStatus.BLOCKED,
                UrlStatus.EXPIRED,
                UrlStatus.INACTIVE,
            ):
                log.info(
                    "url_resolve_non_active",
                    short_code=short_code,
                    status=cached.url_status,
                    schema=schema,
                    source="cache",
                )
                _raise_for_status(cached.url_status)
            if should_sample("cache_operation"):
                log.debug(
                    "url_cache_hit",
                    short_code=short_code,
                    schema=schema,
                    status=cached.url_status,
                )
            return cached, schema

        # 2. Cache miss — dispatch by length and type
        if should_sample("cache_operation"):
            log.debug("url_cache_miss", short_code=short_code)
        url_cache_data, schema = await self._dispatch(short_code)
        if url_cache_data is None:
            log.info("url_resolve_not_found", short_code=short_code)
            raise NotFoundError("URL not found")

        # 3. Populate cache according to caching rules
        await self._populate_cache(short_code, url_cache_data, schema)

        # 4a. Raise for non-ACTIVE v2 (after caching minimal data)
        if schema == SchemaVersion.V2 and url_cache_data.url_status in (
            UrlStatus.BLOCKED,
            UrlStatus.EXPIRED,
            UrlStatus.INACTIVE,
        ):
            log.info(
                "url_resolve_non_active",
                short_code=short_code,
                status=url_cache_data.url_status,
                schema=schema,
                source="db",
            )
            _raise_for_status(url_cache_data.url_status)

        # 4b. Raise for v1 URLs whose max-clicks have been exhausted
        if (
            schema == SchemaVersion.V1
            and url_cache_data.max_clicks is not None
            and url_cache_data.total_clicks >= url_cache_data.max_clicks
        ):
            log.info(
                "url_resolve_expired_max_clicks",
                short_code=short_code,
                total_clicks=url_cache_data.total_clicks,
                max_clicks=url_cache_data.max_clicks,
            )
            raise GoneError("URL has expired (max clicks reached)")

        return url_cache_data, schema

    async def check_alias_available(self, alias: str) -> bool:
        """Return True if alias is free in both urlsV2 and legacy urls collections."""
        if await self._url_repo.check_alias_exists(alias):
            return False
        return not await self._legacy_repo.check_exists(alias)

    async def create(
        self,
        request: CreateUrlRequest,
        owner_id: ObjectId | None,
        client_ip: str,
    ) -> UrlV2Doc:
        """
        Create a new shortened URL.

        Raises:
            ValidationError: URL is invalid, blocked, or field validation fails.
            ConflictError:   The requested alias is already taken.
        """
        now = datetime.now(timezone.utc)

        # 1. Validate the long URL (self-link check + format)
        if not validate_url(
            request.long_url, blocked_self_domains=self._blocked_self_domains
        ):
            log.warning(
                "url_create_rejected",
                reason="invalid_url",
                long_url=request.long_url,
            )
            raise ValidationError("URL is not allowed or invalid", field="long_url")

        # 2. Check against DB blocked patterns
        # validate_blocked_url returns True if allowed, False if blocked
        blocked_patterns = await self._blocked_url_repo.get_patterns()
        if not validate_blocked_url(request.long_url, blocked_patterns):
            log.warning(
                "url_create_rejected",
                reason="blocked_pattern",
                long_url=request.long_url,
            )
            raise ValidationError("URL is blocked", field="long_url")

        # 3. Password hash (cheap — do before alias generation loop)
        password_hash: str | None = None
        if request.password:
            password_hash = hash_password(request.password)

        # 4. expire_after (cheap — validate before alias generation loop)
        expire_ts: datetime | None = None
        if request.expire_after is not None:
            expire_ts = parse_datetime(request.expire_after)
            if expire_ts is None:
                raise ValidationError(
                    "Invalid expire_after format", field="expire_after"
                )
            if expire_ts <= now:
                raise ValidationError(
                    "expire_after must be in the future", field="expire_after"
                )

        # 5. Alias — generate or validate custom (may loop; done after cheap checks)
        if request.alias:
            if not validate_alias(request.alias) and not validate_emoji_alias(
                request.alias
            ):
                raise ValidationError(
                    "Alias contains invalid characters", field="alias"
                )
            if not await self.check_alias_available(request.alias):
                log.info("url_alias_conflict", alias=request.alias)
                raise ConflictError("Alias is already in use")
            alias = request.alias
        else:
            alias = await self._generate_unique_alias()

        # 6. private_stats default depends on auth state
        private_stats: bool | None = request.private_stats
        if private_stats is None:
            private_stats = True if owner_id is not None else None

        # 7. Build document model (validates fields via Pydantic)
        owner_oid = owner_id if owner_id is not None else ANONYMOUS_OWNER_ID
        url_doc = UrlV2Doc(
            alias=alias,
            owner_id=owner_oid,
            created_at=now,
            creation_ip=client_ip,
            long_url=request.long_url,
            password=password_hash,
            block_bots=request.block_bots,
            max_clicks=request.max_clicks,
            expire_after=expire_ts,
            status=UrlStatus.ACTIVE,
            private_stats=private_stats,
            total_clicks=0,
            last_click=None,
        )
        doc = url_doc.model_dump(by_alias=True, exclude={"id"})

        # 8. Insert
        inserted_id = await self._url_repo.insert(doc)
        url_doc.id = inserted_id

        log.info(
            "url_created",
            alias=alias,
            long_url=request.long_url,
            owner_id=str(owner_id) if owner_id else None,
            schema=SchemaVersion.V2,
            has_password=bool(password_hash),
            max_clicks=request.max_clicks,
            block_bots=request.block_bots,
            has_expiration=bool(expire_ts),
            private_stats=private_stats,
        )

        return url_doc

    async def update(
        self,
        url_id: ObjectId,
        request: UpdateUrlRequest,
        owner_id: ObjectId,
    ) -> UrlV2Doc:
        """
        Update an existing URL.

        Raises:
            NotFoundError:  URL doesn't exist.
            ForbiddenError: Caller doesn't own the URL, or URL is blocked.
            ConflictError:  Requested alias is already taken.
            ValidationError: Invalid field values.
        """
        now = datetime.now(timezone.utc)

        # 1. Load existing document
        existing = await self._url_repo.find_by_id(url_id)
        if existing is None:
            raise NotFoundError("URL not found")

        # 2. Ownership check
        if existing.owner_id != owner_id:
            raise ForbiddenError("Access denied: you do not own this URL")

        # 2b. Admin-blocked URLs cannot be modified by the owner
        if existing.status == UrlStatus.BLOCKED:
            raise ForbiddenError("Cannot modify a blocked URL")

        # 3. Build update ops — only changed fields
        update_ops: dict = {}
        fields_set = request.model_fields_set

        if request.long_url is not None and request.long_url != existing.long_url:
            if not validate_url(
                request.long_url, blocked_self_domains=self._blocked_self_domains
            ):
                raise ValidationError("URL is not allowed or invalid", field="long_url")
            update_ops["long_url"] = request.long_url

        if request.alias is not None and request.alias != existing.alias:
            if not await self.check_alias_available(request.alias):
                log.info(
                    "url_alias_conflict",
                    alias=request.alias,
                    url_id=str(url_id),
                )
                raise ConflictError("Alias is already in use")
            update_ops["alias"] = request.alias

        if "password" in fields_set:
            if not request.password and existing.password:
                update_ops["password"] = None
            elif request.password:
                new_hash = hash_password(request.password)
                if new_hash != existing.password:
                    update_ops["password"] = new_hash

        if "max_clicks" in fields_set:
            if (
                request.max_clicks is None or request.max_clicks == 0
            ) and existing.max_clicks:
                update_ops["max_clicks"] = None
            elif request.max_clicks and request.max_clicks != existing.max_clicks:
                update_ops["max_clicks"] = request.max_clicks

        if "expire_after" in fields_set:
            if request.expire_after is None and existing.expire_after:
                update_ops["expire_after"] = None
            elif request.expire_after is not None:
                expire_ts = parse_datetime(request.expire_after)
                if expire_ts is None:
                    raise ValidationError(
                        "Invalid expire_after format", field="expire_after"
                    )
                if expire_ts != existing.expire_after:
                    update_ops["expire_after"] = expire_ts

        if "block_bots" in fields_set:
            if request.block_bots is None and existing.block_bots:
                update_ops["block_bots"] = None
            elif request.block_bots != existing.block_bots:
                update_ops["block_bots"] = request.block_bots

        if "private_stats" in fields_set:
            if request.private_stats is None and existing.private_stats:
                update_ops["private_stats"] = None
            elif request.private_stats != existing.private_stats:
                update_ops["private_stats"] = request.private_stats

        if request.status is not None and request.status != existing.status:
            update_ops["status"] = request.status

        if not update_ops:
            return existing  # No changes detected

        update_ops["updated_at"] = now

        # 4. Persist
        await self._url_repo.update(url_id, {"$set": update_ops})

        # 5. Invalidate cache
        await self._url_cache.invalidate(existing.alias)

        log.info(
            "url_updated",
            url_id=str(url_id),
            alias=existing.alias,
            owner_id=str(owner_id),
            fields_changed=list(update_ops.keys()),
        )

        # Return merged doc (avoids extra DB round-trip)
        merged = existing.model_dump(by_alias=True)
        merged.update(update_ops)
        merged["_id"] = url_id
        return UrlV2Doc.from_mongo(merged)

    async def delete(
        self,
        url_id: ObjectId,
        owner_id: ObjectId,
    ) -> None:
        """
        Delete a URL.

        Raises:
            NotFoundError:  URL doesn't exist.
            ForbiddenError: Caller doesn't own the URL, or URL is blocked.
        """
        existing = await self._url_repo.find_by_id(url_id)
        if existing is None:
            raise NotFoundError("URL not found")

        if existing.owner_id != owner_id:
            raise ForbiddenError("Access denied: you do not own this URL")

        if existing.status == UrlStatus.BLOCKED:
            raise ForbiddenError("Cannot delete a blocked URL")

        await self._url_repo.delete(url_id)
        await self._url_cache.invalidate(existing.alias)

        log.info(
            "url_deleted",
            url_id=str(url_id),
            alias=existing.alias,
            owner_id=str(owner_id),
        )

    async def list_by_owner(
        self,
        owner_id: ObjectId,
        query: ListUrlsQuery,
    ) -> dict:
        """
        Return a paginated list of URLs owned by this user.

        The returned dict matches the current API JSON response shape exactly.
        """
        start_time = time.perf_counter()
        mongo_query: dict = {"owner_id": owner_id}
        f = query.parsed_filter

        if f:
            if f.status:
                mongo_query["status"] = f.status

            date_range: dict = {}
            if f.created_after:
                dt = parse_datetime(f.created_after)
                if dt:
                    date_range["$gte"] = dt
            if f.created_before:
                dt = parse_datetime(f.created_before)
                if dt:
                    date_range["$lte"] = dt
            if date_range:
                mongo_query["created_at"] = date_range

            if f.password_set is True:
                mongo_query["password"] = {"$ne": None}
            elif f.password_set is False:
                mongo_query["password"] = None

            if f.max_clicks_set is True:
                mongo_query["max_clicks"] = {"$ne": None}
            elif f.max_clicks_set is False:
                mongo_query["max_clicks"] = None

            if f.search:
                try:
                    pattern = re.compile(re.escape(f.search), re.IGNORECASE)
                    mongo_query["$or"] = [{"alias": pattern}, {"long_url": pattern}]
                except re.error:
                    raise ValidationError(
                        "Invalid search pattern", field="filter.search"
                    ) from None

        sort_order = (
            -1 if query.sort_order.lower() in ("desc", "descending", "-1") else 1
        )
        skip = (query.page - 1) * query.page_size

        total = await self._url_repo.count_by_query(mongo_query)
        docs = await self._url_repo.find_by_owner(
            query=mongo_query,
            sort_field=query.sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=query.page_size,
        )

        items = [_format_url_list_item(doc) for doc in docs]
        has_next = (skip + len(items)) < total
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        log.info(
            "url_list_query",
            owner_id=str(owner_id),
            page=query.page,
            page_size=query.page_size,
            sort_by=query.sort_by,
            sort_order="descending" if sort_order == -1 else "ascending",
            filter_count=len(mongo_query) - 1,  # subtract the base owner_id filter
            total=total,
            returned=len(items),
            has_next=has_next,
            duration_ms=duration_ms,
        )

        return {
            "items": items,
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "hasNext": has_next,
            "sortBy": query.sort_by,
            "sortOrder": "descending" if sort_order == -1 else "ascending",
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _dispatch(
        self, short_code: str
    ) -> tuple[UrlCacheData | None, SchemaVersion]:
        """
        Determine URL schema and fetch from the appropriate collection.

        Mirrors get_url_by_length_and_type() exactly:
          emoji → emojis, schema "emoji"
          7 chars → urlsV2 first, urls fallback
          6 chars → urls first, urlsV2 fallback
          other   → urlsV2 first, urls fallback
        """
        if validate_emoji_alias(short_code):
            doc = await self._emoji_repo.find_by_id(short_code)
            if doc is not None:
                return _emoji_doc_to_cache(short_code, doc), SchemaVersion.EMOJI
            return None, SchemaVersion.EMOJI

        code_len = len(short_code)
        if code_len == 7:
            return await self._try_v2_then_v1(short_code)
        elif code_len == 6:
            return await self._try_v1_then_v2(short_code)
        else:
            return await self._try_v2_then_v1(short_code)

    async def _try_v2_then_v1(
        self, short_code: str
    ) -> tuple[UrlCacheData | None, SchemaVersion]:
        v2_doc = await self._url_repo.find_by_alias(short_code)
        if v2_doc is not None:
            return _v2_doc_to_cache(v2_doc), SchemaVersion.V2
        v1_doc = await self._legacy_repo.find_by_id(short_code)
        if v1_doc is not None:
            return _legacy_doc_to_cache(short_code, v1_doc), SchemaVersion.V1
        return None, SchemaVersion.V2

    async def _try_v1_then_v2(
        self, short_code: str
    ) -> tuple[UrlCacheData | None, SchemaVersion]:
        v1_doc = await self._legacy_repo.find_by_id(short_code)
        if v1_doc is not None:
            return _legacy_doc_to_cache(short_code, v1_doc), SchemaVersion.V1
        v2_doc = await self._url_repo.find_by_alias(short_code)
        if v2_doc is not None:
            return _v2_doc_to_cache(v2_doc), SchemaVersion.V2
        return None, SchemaVersion.V2

    async def _populate_cache(
        self,
        short_code: str,
        url_cache_data: UrlCacheData,
        schema: str,
    ) -> None:
        """
        Cache the URL data according to caching rules:
          - v2 (any status): cache (minimal for non-ACTIVE)
          - v1 without max-clicks: cache
          - v1 with max-clicks: do NOT cache (total-clicks must be live)
          - emoji: do NOT cache
        """
        if schema == SchemaVersion.V2 or (
            schema == SchemaVersion.V1 and url_cache_data.max_clicks is None
        ):
            await self._url_cache.set(short_code, url_cache_data)

    async def _generate_unique_alias(self) -> str:
        """Generate a 7-character alias not already in urlsV2."""
        for _ in range(10):
            candidate = generate_short_code_v2(7)
            if not await self._url_repo.check_alias_exists(candidate):
                return candidate
        log.error("url_alias_generation_exhausted")
        raise AppError("Could not generate a unique alias; please try again")


# ── Module-level helpers ──────────────────────────────────────────────────────


def _raise_for_status(status: str) -> None:
    if status == UrlStatus.BLOCKED:
        raise BlockedUrlError("URL is blocked")
    raise GoneError("URL has expired or is no longer active")


def _v2_doc_to_cache(doc: UrlV2Doc) -> UrlCacheData:
    return UrlCacheData(
        _id=str(doc.id),
        alias=doc.alias,
        long_url=doc.long_url,
        block_bots=bool(doc.block_bots),
        password_hash=doc.password,
        expiration_time=(
            int(doc.expire_after.timestamp()) if doc.expire_after else None
        ),
        max_clicks=doc.max_clicks,
        url_status=doc.status,
        schema_version=SchemaVersion.V2,
        owner_id=str(doc.owner_id) if doc.owner_id else None,
    )


def _legacy_doc_to_cache(
    short_code: str,
    doc: LegacyUrlDoc | EmojiUrlDoc,
    schema_version: SchemaVersion = SchemaVersion.V1,
) -> UrlCacheData:
    """Convert a LegacyUrlDoc or EmojiUrlDoc to UrlCacheData."""
    expiration_time = None
    if doc.expiration_time:
        expiration_time = int(doc.expiration_time.timestamp())
    return UrlCacheData(
        _id=short_code,
        alias=short_code,
        long_url=doc.url,
        block_bots=bool(doc.block_bots),
        password_hash=doc.password,
        expiration_time=expiration_time,
        max_clicks=doc.max_clicks,
        url_status=UrlStatus.ACTIVE,
        schema_version=schema_version,
        total_clicks=doc.total_clicks,
        owner_id=None,
    )


def _emoji_doc_to_cache(short_code: str, doc: EmojiUrlDoc) -> UrlCacheData:
    return _legacy_doc_to_cache(short_code, doc, schema_version=SchemaVersion.EMOJI)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is UTC-aware. Returns None for None input."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_url_list_item(doc: UrlV2Doc) -> dict:
    """Format a UrlV2Doc for the URL list response."""
    return {
        "id": str(doc.id),
        "alias": doc.alias,
        "long_url": doc.long_url,
        "status": doc.status,
        "created_at": _ensure_utc(doc.created_at),
        "expire_after": int(doc.expire_after.timestamp()) if doc.expire_after else None,
        "max_clicks": doc.max_clicks,
        "private_stats": doc.private_stats,
        "block_bots": bool(doc.block_bots),
        "password_set": doc.password is not None,
        "total_clicks": doc.total_clicks,
        "last_click": _ensure_utc(doc.last_click),
    }
