import os
import redis
from redis.exceptions import RedisError
from utils.logger import get_logger

log = get_logger(__name__)

_redis_instance = None  # singleton


def get_redis() -> redis.Redis:
    global _redis_instance
    if _redis_instance is None:
        redis_uri = os.environ.get("REDIS_URI", None)
        if not redis_uri:
            log.error("redis_uri_not_provided")
            raise RuntimeError("[RedisClient] No REDIS_URI provided.")

        try:
            _redis_instance = redis.Redis.from_url(redis_uri)
            _redis_instance.ping()
            log.info("redis_connected")
        except RedisError as e:
            log.error(
                "redis_connection_failed", error=str(e), error_type=type(e).__name__
            )
            raise e

    return _redis_instance
