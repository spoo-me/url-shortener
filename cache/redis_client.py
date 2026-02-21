import os
from typing import Optional
from walrus import Database, Cache
from redis.exceptions import RedisError
from utils.logger import get_logger

log = get_logger(__name__)

_db: Optional[Database] = None


def get_redis() -> Optional[Database]:
    global _db
    if _db is None:
        redis_uri = os.environ.get("REDIS_URI")
        if not redis_uri:
            log.warning("redis_uri_not_configured")
            return None

        try:
            _db = Database.from_url(redis_uri)
            _db.ping()
            log.info("redis_connected")
        except RedisError as e:
            log.warning(
                "redis_connection_failed", error=str(e), error_type=type(e).__name__
            )
            return None

    return _db


def get_cache() -> Optional[Cache]:
    db = get_redis()
    return db.cache() if db is not None else None
