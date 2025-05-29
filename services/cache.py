import os
from flask_caching import Cache

# Get Redis URL from environment variable, fallback to simple cache if not provided
REDIS_URI = os.environ.get("REDIS_URI", None)

if REDIS_URI:
    # Use Redis cache if URL is provided
    cache_config = {
        "CACHE_TYPE": "redis",
        "CACHE_REDIS_URL": REDIS_URI,
        "CACHE_DEFAULT_TIMEOUT": 300,  # 5 minutes default
        "CACHE_KEY_PREFIX": "spoo_cache:",  # Prefix for cache keys
        "CACHE_REDIS_DB": 0,  # Redis database number
        # Connection pool settings for better performance
        "CACHE_OPTIONS": {
            "connection_pool_kwargs": {
                "max_connections": 50,
            }
        },
    }
else:
    # Fallback to simple cache if Redis is not configured
    cache_config = {"CACHE_TYPE": "simple"}

cache = Cache(config=cache_config)
