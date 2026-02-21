"""
Main cache module.
Initializes the shared CacheStore, UrlCache, and DualCache instances.
"""

from .store import CacheStore
from .dual_cache import DualCache
from .cache_url import UrlCache

cache_store = CacheStore()
cache_query = UrlCache(store=cache_store, ttl_seconds=300)
dual_cache = DualCache(primary_ttl=10 * 60, stale_ttl=60 * 60, lock_ttl=60)
