"""
Agent 3 — Landmark Resolution Agent (OSM Overpass, no LLM)
============================================================
Resolves a landmark string to a precise coordinate using OpenStreetMap's
Overpass API, then fuzzy-matches the POI name using bharataddress's own
phonetic and similarity modules (no new fuzzy-matching logic).

TRIGGER CONDITION:
  - A landmark string was extracted by Agent 1 OR Agent 2, AND
  - We have a candidate center point (pincode centroid from Agent 1/geocoder,
    or previously resolved DIGIPIN).

RADIUS STRATEGY:
  Indian pincodes have a median area of ~90 km². We start with 2 km and
  widen to 5 km if no matching POI is found in the first pass.

FUZZY MATCH:
  Reuses bharataddress.phonetic.normalise() + phonetic.fuzzy_ratio() directly.
  This is the same phonetic engine that handles Gurgaon/Gurugram etc.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# OSM Overpass API endpoint (public, rate-limit respectfully)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# POI types to query in Overpass. Covers the most common Indian landmarks.
_OSM_POI_TAGS = [
    '["amenity"]',
    '["shop"]',
    '["tourism"]',
    '["historic"]',
    '["leisure"]',
    '["office"]',
    '["building"~"yes|commercial|retail"]',
    '["name"]',  # catch-all for named nodes
]

# Phonetic match score threshold — below this we discard the OSM result
_MIN_MATCH_SCORE = 0.55

# Request timeout (seconds)
_REQUEST_TIMEOUT = 8


@dataclass
class OSMCandidate:
    """A single POI returned from Overpass."""
    osm_id:       int
    osm_type:     str  # node / way / relation
    name:         str
    lat:          float
    lon:          float
    match_score:  float = 0.0


@dataclass
class Agent3Result:
    """Result from the Landmark Resolution Agent."""
    triggered:      bool
    landmark_query: Optional[str]
    matched_poi:    Optional[str]
    latitude:       Optional[float]
    longitude:      Optional[float]
    match_score:    float = 0.0
    osm_id:         Optional[int] = None
    search_radius_m: int = 0
    candidates_count: int = 0
    error:          Optional[str] = None


class LandmarkResolutionAgent:
    """
    Agent 3: Resolve landmark string → coordinate via OSM Overpass.
    Uses bharataddress phonetic module for fuzzy name matching.
    """

    def __init__(self, initial_radius_m: int = 2000, max_radius_m: int = 5000):
        self.initial_radius_m = initial_radius_m
        self.max_radius_m     = max_radius_m

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_run(
        self,
        landmark: Optional[str],
        center_lat: Optional[float],
        center_lon: Optional[float],
    ) -> bool:
        """Return True if we have a landmark AND a candidate center."""
        return bool(landmark and center_lat is not None and center_lon is not None)

    def run(
        self,
        landmark: Optional[str],
        center_lat: Optional[float],
        center_lon: Optional[float],
    ) -> tuple[Agent3Result, dict]:
        """
        Query Overpass and fuzzy-match the landmark.

        Returns
        -------
        (Agent3Result, trace_entry)
        """
        if not self.should_run(landmark, center_lat, center_lon):
            return (
                Agent3Result(triggered=False, landmark_query=landmark,
                             matched_poi=None, latitude=None, longitude=None),
                self._trace(0.0, triggered=False),
            )

        t0 = time.perf_counter()

        # Try initial radius, widen if needed
        best: OSMCandidate | None = None
        final_radius = self.initial_radius_m

        for radius in (self.initial_radius_m, self.max_radius_m):
            final_radius = radius
            try:
                candidates = self._query_overpass(landmark, center_lat, center_lon, radius)
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning("Agent3 Overpass query failed: %s", exc)
                return (
                    Agent3Result(
                        triggered=True, landmark_query=landmark,
                        matched_poi=None, latitude=None, longitude=None,
                        error=str(exc),
                    ),
                    self._trace(elapsed_ms, triggered=True, error=str(exc)),
                )

            if candidates:
                best = self._best_match(landmark, candidates)
                if best and best.match_score >= _MIN_MATCH_SCORE:
                    break  # found a good match, no need to widen

        elapsed_ms = (time.perf_counter() - t0) * 1000
        n_candidates = len(candidates) if candidates else 0

        if best and best.match_score >= _MIN_MATCH_SCORE:
            logger.info(
                "Agent3 resolved '%s' → '%s' (score=%.2f) in %.0fms",
                landmark, best.name, best.match_score, elapsed_ms,
            )
            result = Agent3Result(
                triggered        = True,
                landmark_query   = landmark,
                matched_poi      = best.name,
                latitude         = best.lat,
                longitude        = best.lon,
                match_score      = best.match_score,
                osm_id           = best.osm_id,
                search_radius_m  = final_radius,
                candidates_count = n_candidates,
            )
        else:
            logger.info(
                "Agent3: no confident match for '%s' within %dm (%d candidates)",
                landmark, final_radius, n_candidates,
            )
            result = Agent3Result(
                triggered        = True,
                landmark_query   = landmark,
                matched_poi      = None,
                latitude         = None,
                longitude        = None,
                match_score      = best.match_score if best else 0.0,
                search_radius_m  = final_radius,
                candidates_count = n_candidates,
            )

        return result, self._trace(elapsed_ms, triggered=True, n_candidates=n_candidates)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query_overpass(
        self,
        landmark: str,
        lat: float,
        lon: float,
        radius_m: int,
    ) -> list[OSMCandidate]:
        """
        Build an Overpass QL query and return matching POIs.
        We search for nodes/ways with a 'name' tag within the radius circle.
        """
        # Build a union query for various POI types
        # Simple approach: fetch all named elements within radius, then match client-side
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
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            raise RuntimeError(f"Overpass HTTP error: {exc}") from exc

        candidates: list[OSMCandidate] = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name", "").strip()
            if not name:
                continue

            # Coordinate: nodes have lat/lon; ways have center
            if element["type"] == "node":
                elat = element.get("lat")
                elon = element.get("lon")
            else:
                center = element.get("center", {})
                elat = center.get("lat")
                elon = center.get("lon")

            if elat is None or elon is None:
                continue

            candidates.append(OSMCandidate(
                osm_id   = element.get("id", 0),
                osm_type = element["type"],
                name     = name,
                lat      = float(elat),
                lon      = float(elon),
            ))

        return candidates

    @staticmethod
    def _best_match(query: str, candidates: list[OSMCandidate]) -> OSMCandidate | None:
        """
        Score each candidate using bharataddress's phonetic module.
        Returns the highest-scoring candidate (may be below threshold).
        """
        try:
            from bharataddress import phonetic
            use_phonetic = True
        except ImportError:
            use_phonetic = False

        best: OSMCandidate | None = None
        best_score = -1.0

        for c in candidates:
            if use_phonetic:
                score = phonetic.fuzzy_ratio(query, c.name)
                # Also try normalised comparison
                try:
                    norm_q = phonetic.normalise(query)
                    norm_n = phonetic.normalise(c.name)
                    score = max(score, phonetic.fuzzy_ratio(norm_q, norm_n))
                except Exception:
                    pass
            else:
                # Fallback: simple token overlap
                q_tokens = set(query.lower().split())
                n_tokens  = set(c.name.lower().split())
                overlap   = q_tokens & n_tokens
                denom     = max(len(q_tokens), len(n_tokens), 1)
                score     = len(overlap) / denom

            c.match_score = float(score)
            if score > best_score:
                best_score = score
                best = c

        return best

    @staticmethod
    def _trace(
        elapsed_ms: float,
        triggered: bool = True,
        n_candidates: int = 0,
        error: str | None = None,
    ) -> dict:
        return {
            "agent": "Agent3_LandmarkResolution",
            "latency_ms": round(elapsed_ms, 2),
            "approximate_cost_usd": 0.0,  # Overpass is free
            "ran": triggered,
            "candidates_evaluated": n_candidates,
            "error": error,
        }
