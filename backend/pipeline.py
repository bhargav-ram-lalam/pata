"""
Pata Pipeline
=============
resolve_address(raw_address) → AddressResolution

Orchestrates the five agents in order, collecting latency and cost metrics
at every step. The raw address is preserved in the output but comes with a
TTL/expiry for privacy compliance.

Pipeline flow:
  Agent 1 (always)
      ↓
  Agent 2? (if trigger conditions met)
      ↓
  Agent 3? (if landmark + center point available)
      ↓
  Agent 4 (always — but LLM call only if MEDIUM confidence)
      ↓
  Agent 5 (always — validation + DIGIPIN + silent-guess enforcement)
      ↓
  AddressResolution (structured output)
"""
from __future__ import annotations

import datetime
import logging
import time
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from agents.agent1_parser import DeterministicParserAgent
from agents.agent2_ner    import LandmarkNERAgent, get_ner_agent
from agents.agent3_landmark import LandmarkResolutionAgent
from agents.agent4_arbitration import ConfidenceArbitrationAgent
from agents.agent5_selfcheck import SelfCheckAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output schema (Pydantic v2)
# ---------------------------------------------------------------------------

class AddressResolution(BaseModel):
    """
    Structured output of the Pata address resolution pipeline.

    Fields
    ------
    raw_address:         Original input, untouched.
    parsed:              Merged structured fields from Agents 1+2.
    digipin:             10-character India Post geocode (if coord available).
    latitude, longitude: Final arbitrated coordinate.
    confidence:          Final confidence score (0–1) from Agent 4.
    anchor_type:         Geographic anchor source: 'landmark' | 'pincode_centroid' | 'osm_geocode' | 'unresolved'.
    accuracy_radius_meters: Estimated spatial accuracy radius in meters (~150m for landmark, ~2000m for pincode area).
    needs_human_review:  True if confidence is below threshold or checks failed.
    evidence:            Audit trail: which agent produced what.
    pipeline_trace:      Per-agent latency_ms + approximate cost (for reporting).
    timestamp:           ISO-8601 UTC datetime of resolution.
    ttl_for_raw_retention: ISO-8601 datetime after which raw_address must be
                           purged (24 hours post-resolution by default).
    """
    raw_address:   str
    parsed:        dict
    digipin:       Optional[str]  = None
    latitude:      Optional[float] = None
    longitude:     Optional[float] = None
    confidence:    float          = Field(ge=0.0, le=1.0)
    anchor_type:   Optional[str]  = None
    accuracy_radius_meters: Optional[int] = None
    needs_human_review: bool
    evidence:      dict
    pipeline_trace: list[dict]
    timestamp:     str
    ttl_for_raw_retention: str

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Module-level agent singletons (loaded once, reused across calls)
# ---------------------------------------------------------------------------

_agent1: DeterministicParserAgent | None = None
_agent2: LandmarkNERAgent | None = None
_agent3: LandmarkResolutionAgent | None = None
_agent4: ConfidenceArbitrationAgent | None = None
_agent5: SelfCheckAgent | None = None

# TTL for raw address retention (hours)
RAW_ADDRESS_TTL_HOURS = 24


def _init_agents(
    ner_confidence_threshold: float = 0.6,
    llm_provider: str = "anthropic",
    llm_model: str = "claude-haiku-4-5",
) -> None:
    """Initialise singletons on first call."""
    global _agent1, _agent2, _agent3, _agent4, _agent5
    if _agent1 is None:
        _agent1 = DeterministicParserAgent()
    if _agent2 is None:
        _agent2 = get_ner_agent(ner_confidence_threshold)
    if _agent3 is None:
        _agent3 = LandmarkResolutionAgent()
    if _agent4 is None:
        _agent4 = ConfidenceArbitrationAgent(
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
    if _agent5 is None:
        _agent5 = SelfCheckAgent()


def preload_models() -> None:
    """
    Preload models into memory during application startup (FastAPI lifespan)
    to eliminate first-request cold start penalty.
    """
    logger.info("Preloading Pata foundation models...")
    _init_agents()
    if _agent2 is not None:
        _agent2._ensure_model_loaded()
    logger.info("Foundation models successfully preloaded into memory.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def resolve_address(
    raw_address: str,
    *,
    ner_confidence_threshold: float = 0.6,
    llm_provider: str = "anthropic",
    llm_model: str = "claude-haiku-4-5",
    skip_osm: bool = False,
    request_id: Optional[str] = None,
    hint_lat: Optional[float] = None,
    hint_lng: Optional[float] = None,
) -> AddressResolution:
    """
    Resolve a raw Indian address string into a structured AddressResolution.

    Parameters
    ----------
    raw_address:              The original address string (may be messy/incomplete).
    ner_confidence_threshold: Threshold below which Agent 2 (NER) is triggered.
    llm_provider:             "anthropic" | "openai" | "google" (for Agent 4).
    llm_model:                Model name within the chosen provider.
    skip_osm:                 If True, skip Agent 3 (useful for unit tests).
    request_id:               UUID correlation ID for request tracing.
    hint_lat, hint_lng:       Optional user/device GPS hint coordinates.

    Returns
    -------
    AddressResolution (Pydantic model, JSON-serialisable)
    """
    pipeline_start = time.perf_counter()
    if request_id:
        try:
            from observability.logger import request_id_var
            request_id_var.set(request_id)
        except Exception:
            pass

    _init_agents(ner_confidence_threshold, llm_provider, llm_model)

    trace: list[dict] = []
    now_utc  = datetime.datetime.now(datetime.timezone.utc)
    ttl_utc  = now_utc + datetime.timedelta(hours=RAW_ADDRESS_TTL_HOURS)

    # ==================================================================
    # AGENT 1 — Deterministic parser (always)
    # ==================================================================
    a1_result, a1_trace = _agent1.run(raw_address, geocode=True, transliterate=True)
    trace.append(a1_trace)
    logger.info(
        "A1: pincode=%s city=%s conf=%.2f (%.1fms)",
        a1_result.pincode, a1_result.city,
        a1_result.raw_confidence, a1_trace["latency_ms"],
    )

    # ==================================================================
    # AGENT 2 — IndicBERT NER (selective)
    # ==================================================================
    a2_result, a2_trace = _agent2.run(raw_address, a1_result)
    trace.append(a2_trace)
    if a2_result.triggered:
        logger.info(
            "A2: NER triggered, landmark=%s locality=%s (%.0fms)",
            a2_result.landmark, a2_result.locality, a2_trace["latency_ms"],
        )

    # ==================================================================
    # AGENT 3 — Landmark resolution via OSM (selective)
    # ==================================================================
    # Determine the best available landmark and center point
    landmark_for_osm = a2_result.landmark or a1_result.landmark
    center_lat  = a1_result.latitude
    center_lon  = a1_result.longitude

    if skip_osm:
        from agents.agent3_landmark import Agent3Result
        a3_result = Agent3Result(
            triggered=False, landmark_query=landmark_for_osm,
            matched_poi=None, latitude=None, longitude=None,
        )
        a3_trace = {
            "agent": "Agent3_LandmarkResolution",
            "latency_ms": 0.0,
            "approximate_cost_usd": 0.0,
            "ran": False,
            "skipped": "skip_osm=True",
        }
    else:
        a3_result, a3_trace = _agent3.run(landmark_for_osm, center_lat, center_lon)

    trace.append(a3_trace)
    if a3_result.triggered and a3_result.matched_poi:
        logger.info(
            "A3: resolved '%s' → '%s' (score=%.2f, %.0fms)",
            landmark_for_osm, a3_result.matched_poi,
            a3_result.match_score, a3_trace["latency_ms"],
        )

    # ==================================================================
    # AGENT 4 — Confidence arbitration (always; LLM only if MEDIUM)
    # ==================================================================
    a4_result, a4_trace = _agent4.run(raw_address, a1_result, a2_result, a3_result)
    trace.append(a4_trace)
    logger.info(
        "A4: tier=%s conf=%.2f llm=%s (%.1fms)",
        a4_result.tier, a4_result.final_confidence,
        a4_trace.get("llm_called"), a4_trace["latency_ms"],
    )

    # ==================================================================
    # AGENT 5 — Self-check + DIGIPIN generation (always)
    # ==================================================================
    # Build merged fields dict (Agent 1 wins on admin fields, Agent 2 on free-text)
    merged = {
        # Ground truth from Agent 1:
        "pincode":         a1_result.pincode,
        "city":            a1_result.city,
        "district":        a1_result.district,
        "state":           a1_result.state,
        # Free-text from best source:
        "building_number": a2_result.building_number,
        "building_name":   a2_result.building_name,
        "landmark":        a2_result.landmark,
        "locality":        a2_result.locality,
        "sub_locality":    a2_result.sub_locality,
        "road":            a2_result.road,
        "floor":           a2_result.floor,
    }

    final_lat = a4_result.latitude
    final_lon = a4_result.longitude
    final_conf = a4_result.final_confidence
    needs_review = a4_result.needs_human_review

    a5_result, a5_trace = _agent5.run(
        raw_address    = raw_address,
        agent1_result  = a1_result,
        merged_fields  = merged,
        final_lat      = final_lat,
        final_lon      = final_lon,
        final_confidence   = final_conf,
        needs_human_review = needs_review,
    )
    trace.append(a5_trace)

    # Agent 5 may force human review (never clears it)
    if a5_result.force_human_review:
        needs_review = True

    # Use DIGIPIN from Agent 5 if available; fall back to Agent 1's parse-time DIGIPIN
    digipin = a5_result.digipin or a1_result.digipin

    # ==================================================================
    # Build evidence dict
    # ==================================================================
    evidence = {
        "raw_address_preserved": True,
        "request_id": request_id,
        "agent1_digipin_from_parse": a1_result.digipin,
        "agent1_source": "bharataddress_deterministic_parser",
        "agent1_confidence": a1_result.raw_confidence,
        "agent2_triggered": a2_result.triggered,
        "agent2_ner_entities": a2_result.raw_entities if a2_result.triggered else None,
        "agent3_triggered": a3_result.triggered,
        "agent3_landmark_query": a3_result.landmark_query,
        "agent3_matched_poi": a3_result.matched_poi,
        "agent3_osm_id": a3_result.osm_id if a3_result.triggered else None,
        "agent3_match_score": a3_result.match_score if a3_result.triggered else None,
        "agent4_tier": a4_result.tier,
        "agent4_llm_model": a4_result.evidence.get("llm_model"),
        "agent4_llm_choice": a4_result.llm_choice,
        "agent4_llm_reasoning": a4_result.llm_reasoning,
        "agent5_checks": a5_result.checks,
        "agent5_validation_notes": a5_result.validation_notes,
        "combined_confidence": final_conf,
        "coordinate_source": (
            "agent3_osm_poi" if (a3_result.triggered and a3_result.matched_poi
                                 and (a3_result.match_score or 0) >= 0.65)
            else "agent1_pincode_centroid"
        ),
    }

    # Derive anchor_type and estimated accuracy_radius_meters
    # Estimates:
    # - Landmark match (A3): high precision (~150m radius)
    # - Pincode centroid (A1): area estimate (~2000m radius)
    # - Unresolved: None
    if final_lat is None or final_lon is None:
        anchor_type = "unresolved"
        accuracy_radius_meters = None
    elif a3_result.triggered and a3_result.matched_poi and (a3_result.match_score or 0) >= 0.65:
        anchor_type = "landmark"
        accuracy_radius_meters = 150
    elif final_lat is not None and final_lon is not None:
        anchor_type = "pincode_centroid"
        accuracy_radius_meters = 2000
    else:
        anchor_type = "unresolved"
        accuracy_radius_meters = None

    evidence["anchor_type"] = anchor_type
    evidence["accuracy_radius_meters"] = accuracy_radius_meters

    if hint_lat is not None and hint_lng is not None:
        evidence["hint_coordinates"] = {"latitude": hint_lat, "longitude": hint_lng}

    if request_id:
        for t in trace:
            t["request_id"] = request_id

    total_ms = (time.perf_counter() - pipeline_start) * 1000
    total_cost = sum(t.get("approximate_cost_usd", 0.0) for t in trace)
    logger.info(
        "Pipeline complete: %.0fms total, conf=%.2f, review=%s, cost=$%.6f",
        total_ms, final_conf, needs_review, total_cost,
    )

    resolution = AddressResolution(
        raw_address          = raw_address,
        parsed               = merged,
        digipin              = digipin,
        latitude             = final_lat,
        longitude            = final_lon,
        confidence           = final_conf,
        anchor_type          = anchor_type,
        accuracy_radius_meters = accuracy_radius_meters,
        needs_human_review   = needs_review,
        evidence             = evidence,
        pipeline_trace       = trace,
        timestamp            = now_utc.isoformat(),
        ttl_for_raw_retention = ttl_utc.isoformat(),
    )

    try:
        from observability.metrics import record_request_metrics
        record_request_metrics(resolution)
    except Exception:
        pass

    return resolution
