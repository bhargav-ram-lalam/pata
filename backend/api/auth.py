"""
api/auth.py
===========
API Key authentication and Token Bucket rate limiting.

Stage 4: Rate limiting is now Redis-backed (atomic Lua script) when
PATA_REDIS_URL is configured, providing shared state across multiple API
replicas.  Falls back to the original in-memory TokenBucket automatically
when Redis is unavailable (local dev / single-instance).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Set

from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

logger = logging.getLogger(__name__)

# Configured API keys from environment
DEFAULT_KEYS = "pata_dev_key,test_api_key_stage3"
API_KEYS_ENV = os.getenv("PATA_API_KEYS", DEFAULT_KEYS)
VALID_API_KEYS: Set[str] = {k.strip() for k in API_KEYS_ENV.split(",") if k.strip()}

# Rate limiting parameters
RATE_LIMIT_RPS = float(os.getenv("PATA_RATE_LIMIT_RPS", "20.0"))     # Tokens added per second
RATE_LIMIT_BURST = float(os.getenv("PATA_RATE_LIMIT_BURST", "40.0")) # Maximum bucket capacity

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# ---------------------------------------------------------------------------
# Lua script for atomic Redis token-bucket
# ---------------------------------------------------------------------------
# Keys: KEYS[1] = bucket hash key
# Args: ARGV[1]=rate (tokens/sec), ARGV[2]=burst (max tokens),
#       ARGV[3]=now_ms (unix ms), ARGV[4]=cost (tokens to consume, usually 1)
# Returns: 1 if allowed, 0 if denied
_LUA_TOKEN_BUCKET = """
local key      = KEYS[1]
local rate     = tonumber(ARGV[1])
local burst    = tonumber(ARGV[2])
local now_ms   = tonumber(ARGV[3])
local cost     = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_ms')
local tokens   = tonumber(data[1]) or burst
local last_ms  = tonumber(data[2]) or now_ms

local elapsed_sec = (now_ms - last_ms) / 1000.0
tokens = math.min(burst, tokens + elapsed_sec * rate)

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_ms', now_ms)
    redis.call('EXPIRE', key, math.ceil(burst / rate) + 60)
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_ms', now_ms)
    redis.call('EXPIRE', key, math.ceil(burst / rate) + 60)
    return 0
end
"""

_lua_sha: Optional[str] = None
_lua_sha_lock = threading.Lock()


def _get_lua_sha(redis_client) -> str:
    """Load Lua script into Redis once and cache its SHA."""
    global _lua_sha
    with _lua_sha_lock:
        if _lua_sha is None:
            _lua_sha = redis_client.script_load(_LUA_TOKEN_BUCKET)
    return _lua_sha


# ---------------------------------------------------------------------------
# In-memory fallback (unchanged from Stage 3)
# ---------------------------------------------------------------------------

class TokenBucket:
    """Thread-safe Token Bucket for per-client rate limiting (in-memory fallback)."""

    def __init__(self, rate: float = RATE_LIMIT_RPS, burst: float = RATE_LIMIT_BURST):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class RateLimiter:
    """
    Rate limiter per API key.

    Uses Redis-backed token bucket when Redis is available (atomic Lua script,
    race-condition-free under concurrent instances).  Falls back to per-process
    in-memory TokenBucket when Redis is absent (local dev / single instance).

    NOTE: The public `buckets` dict is kept for test compatibility — tests that
    directly inject a TokenBucket into it continue to work via the in-memory path.
    """

    def __init__(self, rate: float = RATE_LIMIT_RPS, burst: float = RATE_LIMIT_BURST):
        self.rate = rate
        self.burst = burst
        # In-memory buckets dict (used as fallback + test injection point)
        self.buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _redis_check(self, api_key: str) -> Optional[bool]:
        """Attempt Redis-backed check. Returns None if Redis unavailable."""
        try:
            from persistence.redis_client import get_redis
            rc = get_redis()
            if rc is None:
                return None
            sha = _get_lua_sha(rc)
            key = f"pata:ratelimit:{api_key}"
            now_ms = int(time.time() * 1000)
            result = rc.evalsha(sha, 1, key, self.rate, self.burst, now_ms, 1)
            return bool(result)
        except Exception as exc:
            logger.warning("Redis rate-limit check failed, using in-memory fallback: %s", exc)
            return None

    def check(self, api_key: str) -> bool:
        # 1. Try Redis (shared across all instances)
        redis_result = self._redis_check(api_key)
        if redis_result is not None:
            return redis_result

        # 2. Fall back to in-memory bucket (single-instance / test path)
        with self._lock:
            if api_key not in self.buckets:
                self.buckets[api_key] = TokenBucket(rate=self.rate, burst=self.burst)
            bucket = self.buckets[api_key]
        return bucket.consume(1.0)


# Global rate limiter singleton
rate_limiter = RateLimiter()


def get_api_key(
    header_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    FastAPI dependency for authenticating requests and applying rate limits.
    Accepts API key via `X-API-Key` header.
    """
    if not header_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Pass 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if header_key not in VALID_API_KEYS:
        logger.warning("Unauthorized request with invalid API key: %s...", header_key[:4])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Apply rate limiting
    if not rate_limiter.check(header_key):
        logger.warning("Rate limit exceeded for API key: %s...", header_key[:4])
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down your requests.",
            headers={"Retry-After": "1"},
        )

    return header_key
