"""
persistence/redis_client.py
===========================
Lazy Redis client singleton with graceful fallback to None.

When PATA_REDIS_URL is unset (local SQLite-only dev), all Redis-backed
components automatically fall back to their in-memory implementations so
tests and local development work without a Redis instance.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client: Optional["redis.Redis"] = None  # type: ignore[name-defined]
_redis_available: Optional[bool] = None

REDIS_URL = os.getenv("PATA_REDIS_URL", "")


def get_redis() -> Optional["redis.Redis"]:  # type: ignore[name-defined]
    """
    Return a connected Redis client, or None if Redis is unavailable/unconfigured.

    Uses a module-level singleton; safe to call from multiple threads — the
    worst case is a brief double-init on first call which is idempotent.
    """
    global _redis_client, _redis_available

    # Short-circuit: previously determined unavailable
    if _redis_available is False:
        return None

    # Short-circuit: already connected
    if _redis_client is not None:
        return _redis_client

    # No URL configured → in-memory fallback
    if not REDIS_URL:
        logger.info(
            "PATA_REDIS_URL not set — Redis-backed components will use in-memory fallbacks "
            "(acceptable for local dev / SQLite mode, not for multi-instance production)."
        )
        _redis_available = False
        return None

    try:
        import redis  # type: ignore[import]

        client = redis.Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        # Verify connectivity
        client.ping()
        _redis_client = client
        _redis_available = True
        logger.info("Redis connected at %s", REDIS_URL)
        return _redis_client

    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s) — falling back to in-memory implementations. "
            "Multi-instance deployments will have per-instance state.",
            exc,
        )
        _redis_available = False
        return None


def reset_redis_client() -> None:
    """Reset the singleton — used in tests to re-evaluate connectivity."""
    global _redis_client, _redis_available
    _redis_client = None
    _redis_available = None
