import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

SYNC_RETRY_SPIKE_CACHE_KEY = "sync_retry_spike_counter"
SYNC_RETRY_SPIKE_WINDOW_SECONDS = 3600


def sync_retry_spike_threshold() -> int:
    raw = getattr(settings, "SYNC_RETRY_SPIKE_THRESHOLD", 5)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 5


def record_sync_retry_event() -> int:
    """
    Increment the rolling 1-hour Redis counter on each outbound sync retry / re-queue.
    Logs logger.critical when the threshold is reached (mirrors Site A retry-spike pattern).
    """
    count = cache.get(SYNC_RETRY_SPIKE_CACHE_KEY, 0)
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    count += 1
    cache.set(SYNC_RETRY_SPIKE_CACHE_KEY, count, timeout=SYNC_RETRY_SPIKE_WINDOW_SECONDS)

    threshold = sync_retry_spike_threshold()
    if count >= threshold:
        logger.critical(
            "[PE ALERT] Outbound sync retry spike: %d event(s) in the last hour "
            "(threshold=%d). Site A may be unreachable or rejecting requests.",
            count,
            threshold,
        )
    return count


def check_sync_retry_spike_sentinel() -> int:
    """Celery Beat backup: re-check counter and alert if still at/above threshold."""
    count = cache.get(SYNC_RETRY_SPIKE_CACHE_KEY, 0)
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0

    threshold = sync_retry_spike_threshold()
    if count >= threshold:
        logger.critical(
            "[PE ALERT] Sentinel: outbound sync retry counter at %d in rolling 1-hour window "
            "(threshold=%d).",
            count,
            threshold,
        )
    return count
