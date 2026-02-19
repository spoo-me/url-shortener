import os
from walrus import Database
from walrus import Cache
from redis.exceptions import RedisError
from utils.logger import get_logger

log = get_logger(__name__)

_db: Database | None = None


def get_redis() -> Database:
    global _db
    if _db is None:
        redis_uri = os.environ.get("REDIS_URI")
        if not redis_uri:
            log.error("redis_uri_not_provided")
            raise RuntimeError("[RedisClient] No REDIS_URI provided.")

        try:
            _db = Database.from_url(redis_uri)
            _db.ping()
            log.info("redis_connected")
        except RedisError as e:
            log.error(
                "redis_connection_failed", error=str(e), error_type=type(e).__name__
            )
            raise e

    return _db


def get_cache() -> Cache:
    return get_redis().cache()
