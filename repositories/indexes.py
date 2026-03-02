"""
MongoDB index and collection setup for all repositories.

Call ensure_indexes(db) once at application startup (from the lifespan handler
in app.py). Index creation is idempotent — safe to call on every boot.

Mirrors the legacy ensure_indexes() in utils/mongo_utils.py exactly,
including every index definition and the time-series collection config.
"""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase

from shared.logging import get_logger

log = get_logger(__name__)


async def ensure_indexes(db: AsyncDatabase) -> None:
    users_col = db["users"]
    urls_v2_col = db["urlsV2"]
    clicks_col = db["clicks"]
    api_keys_col = db["api-keys"]
    tokens_col = db["verification-tokens"]

    # ── users ──────────────────────────────────────────────────────────────
    await users_col.create_index([("email", 1)], unique=True)
    await users_col.create_index(
        [
            ("auth_providers.provider", 1),
            ("auth_providers.provider_user_id", 1),
        ],
        unique=True,
        sparse=True,
    )
    await users_col.create_index([("auth_providers.provider", 1)])

    # ── urlsV2 ─────────────────────────────────────────────────────────────
    await urls_v2_col.create_index([("alias", 1)], unique=True)
    await urls_v2_col.create_index([("owner_id", 1)])
    await urls_v2_col.create_index([("owner_id", 1), ("created_at", -1)])
    await urls_v2_col.create_index([("total_clicks", -1)])
    await urls_v2_col.create_index([("last_click", -1)])

    # ── clicks (time-series) ───────────────────────────────────────────────
    # Create the time-series collection if it doesn't exist yet.
    # Already-existing collection raises OperationFailure — swallow it.
    try:
        await db.create_collection(
            "clicks",
            timeseries={
                "timeField": "clicked_at",
                "metaField": "meta",
                "granularity": "seconds",
            },
        )
    except Exception:
        # Collection already exists — that's fine
        pass

    await clicks_col.create_index([("meta.url_id", 1), ("clicked_at", -1)])
    await clicks_col.create_index([("clicked_at", -1)])
    # CRITICAL: for user-level analytics (scope=all queries)
    await clicks_col.create_index([("meta.owner_id", 1), ("clicked_at", -1)])
    # for anonymous stats (scope=anon, by short_code)
    await clicks_col.create_index([("meta.short_code", 1), ("clicked_at", -1)])

    # ── api-keys ───────────────────────────────────────────────────────────
    await api_keys_col.create_index([("user_id", 1)])
    await api_keys_col.create_index([("token_hash", 1)], unique=True)
    await api_keys_col.create_index([("expires_at", 1)], expireAfterSeconds=0)

    # ── verification-tokens ────────────────────────────────────────────────
    await tokens_col.create_index([("user_id", 1)])
    await tokens_col.create_index([("token_hash", 1)])
    await tokens_col.create_index([("token_type", 1)])
    await tokens_col.create_index([("expires_at", 1)], expireAfterSeconds=0)

    log.info("mongodb_indexes_ensured")
