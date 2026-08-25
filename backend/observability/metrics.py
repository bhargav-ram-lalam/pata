"""
observability/metrics.py
========================
Prometheus metrics registry and telemetry collectors for the Pata address resolution service.

Stage 4 additions:
  - pata_review_queue_size      (Gauge)  — current pending_review count
  - pata_reviews_completed_total (Counter) — labeled confirmed/corrected/rejected
  - pata_review_turnaround_seconds (Histogram) — time from flagged to resolved
"""

from __future__ import annotations

import logging
from typing import Any, Tuple

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

logger = logging.getLogger(__name__)

# Primary Registry
METRICS_REGISTRY = REGISTRY

# ---------------------------------------------------------------------------
# Stage 3 Metric Definitions (unchanged)
# ---------------------------------------------------------------------------

REQUESTS_TOTAL = Counter(
    "pata_requests_total",
    "Total number of address resolution requests processed.",
    ["tier", "status"],
    registry=METRICS_REGISTRY,
)

AGENT_TRIGGERED_TOTAL = Counter(
    "pata_agent_triggered_total",
    "Count of times each pipeline agent was triggered.",
    ["agent_name"],
    registry=METRICS_REGISTRY,
)

AGENT_LATENCY_SECONDS = Histogram(
    "pata_agent_latency_seconds",
    "Execution latency of each agent in seconds.",
    ["agent_name"],
    buckets=(0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0, 2.5, 5.0),
    registry=METRICS_REGISTRY,
)

LLM_CALLS_TOTAL = Counter(
    "pata_llm_calls_total",
    "Total number of Agent 4 LLM disambiguation calls.",
    ["model", "status"],
    registry=METRICS_REGISTRY,
)

LLM_TOKENS_TOTAL = Counter(
    "pata_llm_tokens_total",
    "Total input and output tokens consumed by LLM disambiguation.",
    ["model", "token_type"],  # token_type: "input" | "output"
    registry=METRICS_REGISTRY,
)

OVERPASS_CB_OPEN_TOTAL = Counter(
    "pata_overpass_circuit_breaker_open_total",
    "Total number of times the Overpass circuit breaker tripped to OPEN state.",
    registry=METRICS_REGISTRY,
)

NEEDS_HUMAN_REVIEW_TOTAL = Counter(
    "pata_needs_human_review_total",
    "Total number of addresses flagged for human review.",
    ["reason"],
    registry=METRICS_REGISTRY,
)

# ---------------------------------------------------------------------------
# Stage 4: Human-Review Loop Metrics
# ---------------------------------------------------------------------------

REVIEW_QUEUE_SIZE = Gauge(
    "pata_review_queue_size",
    "Current number of resolutions with review_status='pending_review'.",
    registry=METRICS_REGISTRY,
)

REVIEWS_COMPLETED_TOTAL = Counter(
    "pata_reviews_completed_total",
    "Total number of human reviews completed, by outcome.",
    ["outcome"],  # confirmed | corrected | rejected
    registry=METRICS_REGISTRY,
)

REVIEW_TURNAROUND_SECONDS = Histogram(
    "pata_review_turnaround_seconds",
    "Time from resolution being flagged to human review completion (seconds).",
    buckets=(
        60, 300, 900, 1800,      # 1m, 5m, 15m, 30m
        3600, 7200, 14400,       # 1h, 2h, 4h
        28800, 86400, 259200,    # 8h, 24h, 3d
    ),
    registry=METRICS_REGISTRY,
)


# ---------------------------------------------------------------------------
# Helper Telemetry Functions (Stage 3 — unchanged)
# ---------------------------------------------------------------------------

def record_request_metrics(resolution: Any, status: str = "success") -> None:
    """Record metrics from a completed AddressResolution object or dict."""
    try:
        res_dict = resolution.model_dump() if hasattr(resolution, "model_dump") else (
            resolution.dict() if hasattr(resolution, "dict") else resolution
        )

        tier = res_dict.get("evidence", {}).get("agent4_tier", "unknown").lower()
        REQUESTS_TOTAL.labels(tier=tier, status=status).inc()

        if res_dict.get("needs_human_review"):
            reason = "low_confidence" if res_dict.get("confidence", 0) < 0.50 else "agent_flag"
            if res_dict.get("evidence", {}).get("agent4_llm_choice") == "unresolvable":
                reason = "llm_unresolvable"
            elif "llm_error" in res_dict.get("evidence", {}):
                reason = "llm_error"
            NEEDS_HUMAN_REVIEW_TOTAL.labels(reason=reason).inc()

        for trace in res_dict.get("pipeline_trace", []):
            agent = trace.get("agent", "unknown")
            if trace.get("ran"):
                AGENT_TRIGGERED_TOTAL.labels(agent_name=agent).inc()
                latency_sec = float(trace.get("latency_ms", 0.0)) / 1000.0
                AGENT_LATENCY_SECONDS.labels(agent_name=agent).observe(latency_sec)

    except Exception as exc:
        logger.error("Error recording request metrics: %s", exc)


def record_llm_metrics(model: str, status: str, input_tokens: int, output_tokens: int) -> None:
    """Record LLM token consumption and call counts."""
    try:
        LLM_CALLS_TOTAL.labels(model=model, status=status).inc()
        if input_tokens > 0:
            LLM_TOKENS_TOTAL.labels(model=model, token_type="input").inc(input_tokens)
        if output_tokens > 0:
            LLM_TOKENS_TOTAL.labels(model=model, token_type="output").inc(output_tokens)
    except Exception as exc:
        logger.error("Error recording LLM metrics: %s", exc)


def get_metrics_output() -> Tuple[bytes, str]:
    """Generate Prometheus exposition format payload and content-type."""
    if HAS_PROMETHEUS:
        return generate_latest(METRICS_REGISTRY), CONTENT_TYPE_LATEST
    else:
        return b"# prometheus_client not available\n", "text/plain; version=0.0.4"
