"""
resilience/overpass_client.py
=============================
Hardened Overpass API client with Redis-backed shared caching (Stage 4),
retry backoff, and circuit breaking.

Stage 4 change: OverpassCache now tries Redis first (JSON serialised, EX TTL).
Cache hits are shared across all API replicas instead of each instance warming
its own cold cache.  Falls back to in-memory LRU/TTL when Redis is absent.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Tuple, Any

from resilience.circuit_breaker import CircuitBreaker, RedisCircuitBreaker, CircuitBreakerOpenException

logger = logging.getLogger(__name__)

OVERPASS_URL = os.getenv("PATA_OVERPASS_URL", "https://overpass-api.de/api/interpreter")
CB_FAILURE_THRESHOLD = int(os.getenv("PATA_OVERPASS_CB_THRESHOLD", "3"))
CB_COOLDOWN_SEC = float(os.getenv("PATA_OVERPASS_CB_COOLDOWN_SEC", "60.0"))
OVERPASS_TIMEOUT_SEC = float(os.getenv("PATA_OVERPASS_TIMEOUT_SEC", "1.5"))
OVERPASS_MAX_RETRIES = int(os.getenv("PATA_OVERPASS_MAX_RETRIES", "1"))
CACHE_TTL_SEC = float(os.getenv("PATA_OVERPASS_CACHE_TTL_SEC", "86400.0"))  # 24 hours

_REDIS_KEY_PREFIX = "pata:overpass:"


# ---------------------------------------------------------------------------
# In-memory fallback cache (unchanged from Stage 3)
# ---------------------------------------------------------------------------

class _InMemoryOverpassCache:
    """Thread-safe in-memory cache for Overpass POI candidate lists."""

    def __init__(self, ttl_seconds: float = CACHE_TTL_SEC, max_size: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[Tuple[str, float, float, int], Tuple[float, List[dict]]] = {}
        self._lock = threading.Lock()

    def _make_key(self, landmark: str, lat: float, lon: float, radius_m: int) -> str:
        return f"{landmark.lower().strip()}:{round(lat, 3)}:{round(lon, 3)}:{radius_m}"

    def get(self, landmark: str, lat: float, lon: float, radius_m: int) -> Optional[List[dict]]:
        key = self._make_key(landmark, lat, lon, radius_m)
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None:
                timestamp, data = entry
                if time.time() - timestamp <= self.ttl_seconds:
                    logger.debug("Overpass in-memory cache HIT for key %s", key)
                    return data
                else:
                    del self._cache[key]
        return None

    def set(self, landmark: str, lat: float, lon: float, radius_m: int, data: List[dict]) -> None:
        key = self._make_key(landmark, lat, lon, radius_m)
        with self._lock:
            if len(self._cache) >= self.max_size:
                # Evict oldest entry
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (time.time(), data)


# ---------------------------------------------------------------------------
# Redis-backed cache (shared across replicas)
# ---------------------------------------------------------------------------

class _RedisOverpassCache:
    """
    Redis-backed Overpass cache using JSON serialisation and Redis EX TTL.
    Cache entries are shared across all Pata API replicas — no more per-instance
    cold caches during horizontal scaling.
    """

    def __init__(self, ttl_seconds: float = CACHE_TTL_SEC):
        self.ttl_seconds = int(ttl_seconds)

    @staticmethod
    def _make_key(landmark: str, lat: float, lon: float, radius_m: int) -> str:
        return f"{_REDIS_KEY_PREFIX}{landmark.lower().strip()}:{round(lat, 3)}:{round(lon, 3)}:{radius_m}"

    def get(self, landmark: str, lat: float, lon: float, radius_m: int) -> Optional[List[dict]]:
        from persistence.redis_client import get_redis
        rc = get_redis()
        if rc is None:
            return None
        try:
            key = self._make_key(landmark, lat, lon, radius_m)
            raw = rc.get(key)
            if raw is not None:
                logger.debug("Overpass Redis cache HIT for key %s", key)
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.warning("Redis Overpass cache GET failed: %s", exc)
            return None

    def set(self, landmark: str, lat: float, lon: float, radius_m: int, data: List[dict]) -> None:
        from persistence.redis_client import get_redis
        rc = get_redis()
        if rc is None:
            return
        try:
            key = self._make_key(landmark, lat, lon, radius_m)
            rc.setex(key, self.ttl_seconds, json.dumps(data))
        except Exception as exc:
            logger.warning("Redis Overpass cache SET failed: %s", exc)


# ---------------------------------------------------------------------------
# Unified cache: tries Redis first, falls back to in-memory
# ---------------------------------------------------------------------------

class OverpassCache:
    """
    Unified Overpass POI cache.
    Delegates to Redis when available, otherwise uses in-memory LRU/TTL store.
    API is identical to the Stage 3 in-memory class so all callers are unchanged.
    """

    def __init__(self, ttl_seconds: float = CACHE_TTL_SEC, max_size: int = 1000):
        self._redis = _RedisOverpassCache(ttl_seconds=ttl_seconds)
        self._memory = _InMemoryOverpassCache(ttl_seconds=ttl_seconds, max_size=max_size)

    def get(self, landmark: str, lat: float, lon: float, radius_m: int) -> Optional[List[dict]]:
        result = self._redis.get(landmark, lat, lon, radius_m)
        if result is not None:
            return result
        return self._memory.get(landmark, lat, lon, radius_m)

    def set(self, landmark: str, lat: float, lon: float, radius_m: int, data: List[dict]) -> None:
        self._redis.set(landmark, lat, lon, radius_m, data)
        self._memory.set(landmark, lat, lon, radius_m, data)


# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------

overpass_circuit_breaker = RedisCircuitBreaker(
    name="OverpassAPI",
    failure_threshold=CB_FAILURE_THRESHOLD,
    cooldown_seconds=CB_COOLDOWN_SEC,
)
overpass_cache = OverpassCache()


# ---------------------------------------------------------------------------
# Raw HTTP request (unchanged)
# ---------------------------------------------------------------------------

def fetch_overpass_candidates_raw(
    landmark: str,
    lat: float,
    lon: float,
    radius_m: int,
    timeout: float = OVERPASS_TIMEOUT_SEC,
) -> List[dict]:
    """Execute raw HTTP request to Overpass API."""
    query = f"""
[out:json][timeout:10];
(
  node["name"](around:{radius_m},{lat},{lon});
  way["name"](around:{radius_m},{lat},{lon});
);
out center 100;
"""
    encoded = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=encoded,
        headers={"User-Agent": "Pata-AddressResolver/1.0 (contact@pata.ai)"},
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())

    candidates = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue

        if element["type"] == "node":
            elat = element.get("lat")
            elon = element.get("lon")
        else:
            center = element.get("center", {})
            elat = center.get("lat")
            elon = center.get("lon")

        if elat is None or elon is None:
            continue

        candidates.append({
            "osm_id": element.get("id", 0),
            "osm_type": element["type"],
            "name": name,
            "lat": float(elat),
            "lon": float(elon),
        })

    return candidates


def query_overpass_with_resilience(
    landmark: str,
    lat: float,
    lon: float,
    radius_m: int,
    timeout: float = OVERPASS_TIMEOUT_SEC,
    max_retries: int = OVERPASS_MAX_RETRIES,
) -> List[dict]:
    """
    Fetch POI candidates with Redis-shared caching, retry with backoff,
    and circuit breaker protection.
    Returns empty list if circuit breaker is open or all retries fail.
    """
    # 1. Check cache (Redis → in-memory)
    cached = overpass_cache.get(landmark, lat, lon, radius_m)
    if cached is not None:
        return cached

    # 2. Check circuit breaker state
    if overpass_circuit_breaker.state.value == "OPEN":
        logger.warning(
            "Overpass circuit breaker is OPEN. Skipping Overpass query for '%s' (fallback to centroid).",
            landmark,
        )
        return []

    # 3. Retry loop under circuit breaker
    last_error: Exception | None = None
    backoff = 0.5

    for attempt in range(max_retries + 1):
        try:
            candidates = overpass_circuit_breaker.call(
                fetch_overpass_candidates_raw,
                landmark,
                lat,
                lon,
                radius_m,
                timeout,
            )
            # Store in both Redis and in-memory cache
            overpass_cache.set(landmark, lat, lon, radius_m, candidates)
            return candidates
        except CircuitBreakerOpenException:
            logger.warning("Overpass call aborted: circuit breaker OPEN.")
            return []
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Overpass attempt %d/%d failed for '%s': %s",
                attempt + 1, max_retries + 1, landmark, exc,
            )
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2.0

    logger.error("Overpass query failed after %d retries for '%s': %s", max_retries + 1, landmark, last_error)
    return []
