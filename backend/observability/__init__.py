"""
Observability package for Pata.
Provides Prometheus metrics exposition and structured JSON logging.
"""

from observability.metrics import (
    REQUESTS_TOTAL,
    AGENT_TRIGGERED_TOTAL,
    AGENT_LATENCY_SECONDS,
    LLM_CALLS_TOTAL,
    LLM_TOKENS_TOTAL,
    OVERPASS_CB_OPEN_TOTAL,
    NEEDS_HUMAN_REVIEW_TOTAL,
    record_request_metrics,
    record_llm_metrics,
    get_metrics_output,
)
from observability.logger import get_logger, JSONLogFormatter

__all__ = [
    "REQUESTS_TOTAL",
    "AGENT_TRIGGERED_TOTAL",
    "AGENT_LATENCY_SECONDS",
    "LLM_CALLS_TOTAL",
    "LLM_TOKENS_TOTAL",
    "OVERPASS_CB_OPEN_TOTAL",
    "NEEDS_HUMAN_REVIEW_TOTAL",
    "record_request_metrics",
    "record_llm_metrics",
    "get_metrics_output",
    "get_logger",
    "JSONLogFormatter",
]
