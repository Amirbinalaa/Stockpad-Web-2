import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("api")

WM_CATALOG_KEY_PREFIX = "wm_catalog_"
_WM_CATALOG_REGISTRY = "_wm_catalog_key_registry"


def register_wm_catalog_key(cache_key: str) -> None:
    """Track wm_catalog keys so sync can invalidate them without cache.clear()."""
    registry = cache.get(_WM_CATALOG_REGISTRY)
    if registry is None:
        registry = []
    elif not isinstance(registry, list):
        registry = list(registry)
    if cache_key not in registry:
        registry.append(cache_key)
        cache.set(_WM_CATALOG_REGISTRY, registry, timeout=None)


def invalidate_wm_catalog_cache() -> int:
    """
    Delete all wm_catalog_{email} entries without touching other cache keys
    (e.g. ai_inventory_insights_{email}, per-user dashboard caches).
    """
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if "redis" in backend.lower():
        deleted = _invalidate_wm_catalog_redis()
    else:
        deleted = _invalidate_wm_catalog_registry()
    logger.info("Invalidated %d wm_catalog cache key(s).", deleted)
    return deleted


def _invalidate_wm_catalog_registry() -> int:
    registry = cache.get(_WM_CATALOG_REGISTRY)
    if not registry:
        return 0
    keys = list(registry)
    cache.delete_many(keys)
    cache.delete(_WM_CATALOG_REGISTRY)
    return len(keys)


def _invalidate_wm_catalog_redis() -> int:
    import redis

    location = settings.CACHES["default"]["LOCATION"]
    if isinstance(location, (list, tuple)):
        location = location[0]

    key_prefix = settings.CACHES["default"].get("KEY_PREFIX", "")
    version = settings.CACHES["default"].get("VERSION", 1)
    pattern = f"{key_prefix}{version}:{WM_CATALOG_KEY_PREFIX}*"

    client = redis.from_url(location)
    deleted = 0
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            deleted += client.delete(*keys)
        if cursor == 0:
            break

    cache.delete(_WM_CATALOG_REGISTRY)
    return deleted
