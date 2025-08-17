import os
import redis
from redis.exceptions import RedisError

_redis_instance = None  # singleton


def get_redis() -> redis.Redis:
    global _redis_instance
    if _redis_instance is None:
        redis_uri = os.environ.get("REDIS_URI", None)
        if not redis_uri:
            raise RuntimeError("[RedisClient] No REDIS_URI provided.")

        try:
            _redis_instance = redis.Redis.from_url(redis_uri)
            _redis_instance.ping()
            print("[RedisClient] Connected successfully.")
        except RedisError as e:
            print(f"[RedisClient] Redis connection failed: {e}")
            raise e

    return _redis_instance
