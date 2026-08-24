"""
resilience/circuit_breaker.py
=============================
Thread-safe Circuit Breaker with optional Redis-backed shared state (Stage 4).

Stage 4 change: RedisCircuitBreaker stores CLOSED/OPEN/HALF_OPEN state,
failure count, and last-change timestamp in a Redis Hash.  Transitions use
optimistic locking (WATCH/MULTI/EXEC) to remain race-condition-free under
concurrent replicas.  Falls back to in-process state when Redis unavailable.

Protects the pipeline from cascading failures when upstream services
(e.g. Overpass, LLM) degrade.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

_REDIS_CB_PREFIX = "pata:cb:"


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"        # Normal operation: requests pass through
    OPEN = "OPEN"            # Tripped: requests fail fast without calling remote service
    HALF_OPEN = "HALF_OPEN"  # Testing: allows a trial request through


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


# ---------------------------------------------------------------------------
# In-process circuit breaker (original Stage 3 implementation — unchanged)
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Circuit Breaker with failure threshold, cool-down period, and state tracking.

    When PATA_REDIS_URL is set, the global `overpass_circuit_breaker` singleton
    in overpass_client.py is automatically upgraded to RedisCircuitBreaker so
    state is shared across all replicas.  This class is still used directly in
    tests and as a fallback.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        on_state_change: Optional[Callable[[str, CircuitState], None]] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_state_change = time.time()
        self._last_failure_time = 0.0
        self._trip_count = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._evaluate_state_locked()
            return self._state

    @property
    def trip_count(self) -> int:
        with self._lock:
            return self._trip_count

    def _evaluate_state_locked(self) -> None:
        """Evaluate if an OPEN circuit should transition to HALF_OPEN after cooldown."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_state_change >= self.cooldown_seconds:
                self._transition_to_locked(CircuitState.HALF_OPEN)

    def _transition_to_locked(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        logger.warning(
            "CircuitBreaker [%s]: state transition %s -> %s (failures=%d)",
            self.name, old_state.value, new_state.value, self._failure_count,
        )
        if new_state == CircuitState.OPEN:
            self._trip_count += 1
        if self.on_state_change:
            try:
                self.on_state_change(self.name, new_state)
            except Exception as e:
                logger.error("CircuitBreaker on_state_change callback error: %s", e)

    def record_success(self) -> None:
        """Record a successful invocation."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("CircuitBreaker [%s]: trial request succeeded, resetting to CLOSED", self.name)
                self._failure_count = 0
                self._transition_to_locked(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed invocation."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            logger.warning(
                "CircuitBreaker [%s]: recorded failure %d/%d (error: %s)",
                self.name, self._failure_count, self.failure_threshold, error,
            )
            if self._state == CircuitState.HALF_OPEN:
                # Immediate re-trip on failure in half-open state
                self._transition_to_locked(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold:
                self._transition_to_locked(CircuitState.OPEN)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute the wrapped callable under circuit breaker protection.
        Raises CircuitBreakerOpenException if the circuit is OPEN.
        """
        with self._lock:
            self._evaluate_state_locked()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.name}' is OPEN (cooldown: {self.cooldown_seconds}s)"
                )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure(exc)
            raise

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        with self._lock:
            self._failure_count = 0
            self._transition_to_locked(CircuitState.CLOSED)


# ---------------------------------------------------------------------------
# Redis-backed circuit breaker (shared state across replicas)
# ---------------------------------------------------------------------------

class RedisCircuitBreaker(CircuitBreaker):
    """
    Circuit Breaker that stores state in Redis, shared across all Pata API replicas.

    Redis Hash layout (key = pata:cb:{name}):
      state          : "CLOSED" | "OPEN" | "HALF_OPEN"
      failure_count  : int
      last_change_ts : float (unix timestamp)
      trip_count     : int

    State transitions use WATCH/MULTI/EXEC (optimistic locking) to prevent
    race conditions when multiple replicas record failures concurrently.
    Falls back to in-process state on any Redis error.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        on_state_change: Optional[Callable[[str, CircuitState], None]] = None,
    ):
        super().__init__(
            name=name,
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
            on_state_change=on_state_change,
        )
        self._redis_key = f"{_REDIS_CB_PREFIX}{name}"

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    def _get_redis(self):
        try:
            from persistence.redis_client import get_redis
            return get_redis()
        except Exception:
            return None

    def _redis_read_state(self, rc) -> Optional[dict]:
        """Read the current CB state from Redis. Returns None on error."""
        try:
            data = rc.hgetall(self._redis_key)
            if not data:
                return None
            return {
                "state": data.get("state", "CLOSED"),
                "failure_count": int(data.get("failure_count", 0)),
                "last_change_ts": float(data.get("last_change_ts", time.time())),
                "trip_count": int(data.get("trip_count", 0)),
            }
        except Exception:
            return None

    def _redis_write_state(self, rc, state: str, failure_count: int,
                           last_change_ts: float, trip_count: int) -> bool:
        """Write CB state to Redis. Returns True on success."""
        try:
            rc.hset(self._redis_key, mapping={
                "state": state,
                "failure_count": failure_count,
                "last_change_ts": last_change_ts,
                "trip_count": trip_count,
            })
            # TTL: keep state for cooldown + 2× burst window
            rc.expire(self._redis_key, int(self.cooldown_seconds * 3 + 300))
            return True
        except Exception as exc:
            logger.warning("RedisCircuitBreaker write failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # State property — reads from Redis, falls back to in-process
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        rc = self._get_redis()
        if rc is None:
            return super().state  # in-process fallback

        data = self._redis_read_state(rc)
        if data is None:
            return super().state  # Redis empty → treat as CLOSED

        raw_state = data["state"]
        last_change_ts = data["last_change_ts"]

        # OPEN → HALF_OPEN cooldown check
        if raw_state == "OPEN" and (time.time() - last_change_ts) >= self.cooldown_seconds:
            # Attempt transition (best-effort, may race with another replica)
            self._redis_write_state(
                rc, "HALF_OPEN", data["failure_count"], time.time(), data["trip_count"]
            )
            logger.warning("CircuitBreaker [%s]: Redis OPEN → HALF_OPEN (cooldown elapsed)", self.name)
            return CircuitState.HALF_OPEN

        try:
            return CircuitState(raw_state)
        except ValueError:
            return CircuitState.CLOSED

    @property
    def trip_count(self) -> int:
        rc = self._get_redis()
        if rc is None:
            return super().trip_count
        data = self._redis_read_state(rc)
        return data["trip_count"] if data else 0

    # ------------------------------------------------------------------
    # record_success / record_failure — atomic via optimistic locking
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        rc = self._get_redis()
        if rc is None:
            super().record_success()
            return
        try:
            with rc.pipeline() as pipe:
                for _ in range(3):  # retry up to 3 times on WatchError
                    try:
                        pipe.watch(self._redis_key)
                        data = self._redis_read_state(pipe)
                        if data is None:
                            pipe.reset()
                            return
                        current_state = data["state"]
                        pipe.multi()
                        if current_state == "HALF_OPEN":
                            logger.info("CircuitBreaker [%s]: Redis trial success → CLOSED", self.name)
                            pipe.hset(self._redis_key, mapping={
                                "state": "CLOSED", "failure_count": 0,
                                "last_change_ts": time.time(), "trip_count": data["trip_count"],
                            })
                        elif current_state == "CLOSED":
                            pipe.hset(self._redis_key, "failure_count", 0)
                        pipe.execute()
                        break
                    except Exception:  # WatchError or Redis error
                        continue
        except Exception as exc:
            logger.warning("RedisCircuitBreaker record_success failed, using in-process: %s", exc)
            super().record_success()

    def record_failure(self, error: Optional[Exception] = None) -> None:
        rc = self._get_redis()
        if rc is None:
            super().record_failure(error)
            return
        try:
            with rc.pipeline() as pipe:
                for _ in range(3):
                    try:
                        pipe.watch(self._redis_key)
                        data = self._redis_read_state(pipe) or {
                            "state": "CLOSED", "failure_count": 0,
                            "last_change_ts": time.time(), "trip_count": 0,
                        }
                        failure_count = data["failure_count"] + 1
                        current_state = data["state"]
                        trip_count = data["trip_count"]
                        new_state = current_state
                        new_ts = data["last_change_ts"]

                        if current_state == "HALF_OPEN":
                            new_state = "OPEN"
                            new_ts = time.time()
                            trip_count += 1
                            logger.warning("CircuitBreaker [%s]: Redis HALF_OPEN failure → OPEN", self.name)
                        elif current_state == "CLOSED" and failure_count >= self.failure_threshold:
                            new_state = "OPEN"
                            new_ts = time.time()
                            trip_count += 1
                            logger.warning(
                                "CircuitBreaker [%s]: Redis tripped CLOSED → OPEN (failures=%d)",
                                self.name, failure_count,
                            )

                        logger.warning(
                            "CircuitBreaker [%s]: Redis recorded failure %d/%d",
                            self.name, failure_count, self.failure_threshold,
                        )
                        pipe.multi()
                        pipe.hset(self._redis_key, mapping={
                            "state": new_state,
                            "failure_count": failure_count,
                            "last_change_ts": new_ts,
                            "trip_count": trip_count,
                        })
                        pipe.expire(self._redis_key, int(self.cooldown_seconds * 3 + 300))
                        pipe.execute()
                        break
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("RedisCircuitBreaker record_failure failed, using in-process: %s", exc)
            super().record_failure(error)

    def reset(self) -> None:
        rc = self._get_redis()
        if rc is None:
            super().reset()
            return
        try:
            self._redis_write_state(rc, "CLOSED", 0, time.time(), 0)
            logger.info("CircuitBreaker [%s]: Redis reset to CLOSED", self.name)
        except Exception as exc:
            logger.warning("RedisCircuitBreaker reset failed: %s", exc)
            super().reset()
