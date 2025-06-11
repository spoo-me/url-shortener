"""
Main cache module.
Intializes the cache query and dual cache instances.
"""

from .dual_cache import DualCache
from .cache_url import UrlCache

cache_query = UrlCache(ttl_seconds=300)
dual_cache = DualCache(primary_ttl=300, stale_ttl=900, lock_ttl=30)
