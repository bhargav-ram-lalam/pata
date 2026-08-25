"""
Agent 5 — Self-Check Agent (final validation pass)
====================================================
Before returning the result, performs five sanity checks:

  1. Does the final coordinate fall within the claimed pincode's
     centroid ± radius? (catches wild misfires from Agent 3)
  2. Is a DIGIPIN present for the final coordinate?
     Generates one if lat/lon are available.
  3. Is the evidence trail complete?
     (raw input, which landmark/pincode produced each field)
  4. Is confidence below the silent-guess threshold?
     If so, was it correctly flagged? (hard assertion)
  5. Reuses bharataddress.validate() / is_deliverable() for
     administrative cross-validation (state/district/city vs pincode).

All checks are logged and included in the returned validation_notes dict.
This agent NEVER alters field values — it only adds metadata and can
upgrade needs_human_review from False → True (never the reverse).
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Max distance (km) a resolved point can be from the pincode centroid
# before we flag it as suspicious. Chosen to cover large rural pincodes.
MAX_CENTROID_DISTANCE_KM = 50.0

# If overall confidence drops below this, the address MUST be flagged for review.
SILENT_GUESS_THRESHOLD = 0.50


@dataclass
class Agent5Result:
    """Metadata added by the Self-Check Agent."""
    digipin:           Optional[str]
    is_deliverable:    bool
    checks:            dict = field(default_factory=dict)
    validation_notes:  list = field(default_factory=list)
    # Override flag: True if any check failed that requires human review
    force_human_review: bool = False


class SelfCheckAgent:
    """
    Agent 5: Final validation pass.
    Uses bharataddress.validate() and bharataddress.digipin.
    """

    def run(
        self,
        raw_address: str,
        agent1_result,       # Agent1Result
        merged_fields: dict, # the merged address fields dict
        final_lat: Optional[float],
        final_lon: Optional[float],
        final_confidence: float,
        needs_human_review: bool,
    ) -> tuple[Agent5Result, dict]:
        """
        Run all five checks.

        Parameters
        ----------
        merged_fields:     Dict of merged address fields (after Agent 2 merge).
        final_lat/lon:     The final arbitrated coordinate (may be None).
        final_confidence:  The confidence from Agent 4.
        needs_human_review: Current review flag (may be upgraded, never cleared).

        Returns
        -------
        (Agent5Result, trace_entry)
        """
        t0 = time.perf_counter()
        notes: list[str] = []
        checks: dict = {}
        force_review = False

        # ------------------------------------------------------------------
        # Check 1: Coordinate within pincode centroid radius
        # ------------------------------------------------------------------
        checks["coord_within_pincode_radius"] = None  # unknown if no coord
        if final_lat is not None and agent1_result.latitude is not None:
            dist_km = _haversine_km(
                final_lat, final_lon,
                agent1_result.latitude, agent1_result.longitude,
            )
            within = dist_km <= MAX_CENTROID_DISTANCE_KM
            checks["coord_within_pincode_radius"] = within
            checks["coord_distance_from_centroid_km"] = round(dist_km, 2)
            if not within:
                notes.append(
                    f"WARNING: resolved coordinate is {dist_km:.1f} km from "
                    f"pincode centroid (>{MAX_CENTROID_DISTANCE_KM} km threshold)"
                )
                force_review = True
                logger.warning(
                    "Agent5 Check1 FAIL: coord %.4f,%.4f is %.1fkm from "
                    "pincode %s centroid",
                    final_lat, final_lon, dist_km, agent1_result.pincode,
                )

        # ------------------------------------------------------------------
        # Check 2: DIGIPIN generation
        # ------------------------------------------------------------------
        digipin: Optional[str] = None
        checks["digipin_generated"] = False
        if final_lat is not None and final_lon is not None:
            try:
                from bharataddress import digipin as ba_digipin
                digipin = ba_digipin.encode(final_lat, final_lon)
                checks["digipin_generated"] = True
                checks["digipin"] = digipin
            except Exception as exc:
                notes.append(f"DIGIPIN generation failed: {exc}")
                logger.warning("Agent5 Check2: digipin.encode() failed: %s", exc)

        # ------------------------------------------------------------------
        # Check 3: Evidence trail completeness
        # ------------------------------------------------------------------
        required_evidence_keys = ["raw_address", "combined_confidence"]
        # These will be checked in pipeline.py where we have the full evidence
        # dict. Here we just verify critical fields are non-None.
        missing_fields = [
            k for k in ("pincode", "city", "state")
            if not merged_fields.get(k)
        ]
        checks["critical_fields_present"] = len(missing_fields) == 0
        if missing_fields:
            notes.append(f"Missing critical fields: {missing_fields}")

        # ------------------------------------------------------------------
        # Check 4: Silent-guess enforcement
        # ------------------------------------------------------------------
        if final_confidence < SILENT_GUESS_THRESHOLD and not needs_human_review:
            # This should never happen if Agent 4 is correct — hard assertion
            notes.append(
                f"CRITICAL: confidence={final_confidence:.3f} is below "
                f"silent-guess threshold ({SILENT_GUESS_THRESHOLD}) but "
                f"needs_human_review=False — overriding to True"
            )
            force_review = True
            logger.error(
                "Agent5 Check4 FAIL: low confidence not flagged! Overriding."
            )
        checks["silent_guess_enforced"] = final_confidence >= SILENT_GUESS_THRESHOLD or needs_human_review

        # ------------------------------------------------------------------
        # Check 5: bharataddress administrative validation
        # ------------------------------------------------------------------
        is_deliverable = False
        checks["ba_validation_passed"] = None
        try:
            from bharataddress import parse as ba_parse, validate as ba_validate
            from bharataddress import is_deliverable as ba_is_deliverable

            # Re-parse using the merged pincode if available to get a validated object
            query = " ".join(filter(None, [
                merged_fields.get("pincode"),
                merged_fields.get("city"),
                merged_fields.get("state"),
            ]))
            if query.strip():
                p = ba_parse(query)
                v = ba_validate(p)
                is_deliverable = ba_is_deliverable(p)
                checks["ba_validation_passed"] = v.get("is_deliverable", False)
                checks["ba_validation_issues"] = v.get("issues", [])
                if v.get("issues"):
                    notes.append(f"bharataddress validation issues: {v['issues']}")
        except Exception as exc:
            logger.warning("Agent5 Check5: ba_validate() failed: %s", exc)
            checks["ba_validation_passed"] = None

        elapsed_ms = (time.perf_counter() - t0) * 1000

        result = Agent5Result(
            digipin           = digipin,
            is_deliverable    = is_deliverable,
            checks            = checks,
            validation_notes  = notes,
            force_human_review = force_review,
        )
        return result, self._trace(elapsed_ms)

    @staticmethod
    def _trace(elapsed_ms: float) -> dict:
        return {
            "agent": "Agent5_SelfCheck",
            "latency_ms": round(elapsed_ms, 2),
            "approximate_cost_usd": 0.0,
            "ran": True,
        }


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
