"""
Agent 1 — Deterministic Parser Agent
=====================================
Wraps bharataddress.parse(). Runs on 100% of requests, always first.

- Target latency: <10ms (bharataddress claims ~5ms)
- Zero cost — purely deterministic, no network, no ML
- Returns ParsedAddress + per-field confidence dict
- Pincode/city/district/state fields are "ground truth" from India Post lookup
"""
from __future__ import annotations

import logging
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Landmark cue words bharataddress uses for detection (from its rules engine).
# We surface these so Agent 2 can decide whether to run even when confidence is
# technically above threshold (raw string has cue words but parser missed them).
LANDMARK_CUE_WORDS = frozenset([
    "near", "opp", "opposite", "behind", "beside", "next to",
    "adjacent", "in front", "paas", "samne", "peeche", "bagal",
    "niche", "upar", "ke paas", "ke samne", "ke peeche",
])

# Devanagari Unicode block: U+0900–U+097F
_DEVANAGARI_START = 0x0900
_DEVANAGARI_END   = 0x097F


def _has_devanagari(text: str) -> bool:
    """Return True if the string contains any Devanagari characters."""
    return any(_DEVANAGARI_START <= ord(c) <= _DEVANAGARI_END for c in text)


def _has_landmark_cue(text: str) -> bool:
    """Return True if the raw string contains any landmark cue words."""
    lower = text.lower()
    return any(cue in lower for cue in LANDMARK_CUE_WORDS)


@dataclass
class Agent1Result:
    """Structured result from the Deterministic Parser Agent."""
    # bharataddress ParsedAddress fields (all optional at source)
    building_number:  Optional[str]
    building_name:    Optional[str]
    landmark:         Optional[str]
    locality:         Optional[str]
    sub_locality:     Optional[str]
    city:             Optional[str]
    district:         Optional[str]
    state:            Optional[str]
    pincode:          Optional[str]
    # Geocode from embedded centroid (if available)
    latitude:         Optional[float]
    longitude:        Optional[float]
    # DIGIPIN from parse() — already computed by bharataddress when geocode=True
    digipin:          Optional[str] = None
    # bharataddress's own scalar confidence (0–1)
    raw_confidence:   float = 0.0
    # Per-field confidence derived from bharataddress validator
    field_confidence: dict = field(default_factory=dict)
    # Flags for downstream agents
    has_devanagari:   bool = False
    has_landmark_cue: bool = False
    # The cleaned string bharataddress produced
    cleaned:          Optional[str] = None

    def freetext_min_confidence(self) -> float:
        """
        Minimum confidence across the four free-text fields that Agent 2
        can improve: landmark, locality, building_name, sub_locality.
        """
        keys = ["landmark", "locality", "building_name", "sub_locality"]
        values = [self.field_confidence.get(k, 0.0) for k in keys]
        return min(values)

    def to_dict(self) -> dict:
        return {
            "building_number": self.building_number,
            "building_name":   self.building_name,
            "landmark":        self.landmark,
            "locality":        self.locality,
            "sub_locality":    self.sub_locality,
            "city":            self.city,
            "district":        self.district,
            "state":           self.state,
            "pincode":         self.pincode,
            "latitude":        self.latitude,
            "longitude":       self.longitude,
        }


class DeterministicParserAgent:
    """
    Agent 1: Wraps bharataddress deterministic parser.

    Per-field confidence heuristics:
      - pincode/state/district/city → use bharataddress's validate() output
        (these are directory lookups, treat as ground truth: 0.96–0.99)
      - landmark/locality           → 0.85 if field is non-None, else 0.0
        (bharataddress landmark F1 ~0.92, locality F1 ~0.81 — weighted down
         slightly because we can't get per-instance confidence from it)
      - building_name               → 0.55 if non-None, else 0.0  (F1 ~0.73)
      - sub_locality                → 0.35 if non-None, else 0.0  (F1 ~0.46–0.73)
    """

    # These constants encode the per-field F1 scores from the README.
    # We use them as the "assumed" confidence when a field is present.
    _FIELD_PRESENT_CONFIDENCE = {
        "pincode":         0.99,
        "state":           0.98,
        "district":        0.97,
        "city":            0.96,
        "building_number": 0.95,
        "landmark":        0.88,
        "locality":        0.82,
        "building_name":   0.62,
        "sub_locality":    0.40,
    }

    def run(
        self,
        raw_address: str,
        geocode: bool = True,
        transliterate: bool = True,
    ) -> tuple[Agent1Result, dict]:
        """
        Parse the raw address string.

        Parameters
        ----------
        raw_address:    The original, unmodified address string.
        geocode:        If True, pass geocode=True to bharataddress to get
                        pincode centroid from its embedded DB (no network).
        transliterate:  If True and Devanagari is detected, pass
                        transliterate=True to bharataddress (requires
                        bharataddress[indic] extra).

        Returns
        -------
        (Agent1Result, trace_entry)  where trace_entry is the pipeline_trace
        dict for this agent.
        """
        t0 = time.perf_counter()

        has_dev = _has_devanagari(raw_address)
        has_cue = _has_landmark_cue(raw_address)

        # -- Import bharataddress here so the module can be imported even if
        #    bharataddress isn't installed (tests can mock it).
        try:
            from bharataddress import parse as ba_parse
            from bharataddress import validate as ba_validate
        except ImportError as exc:
            raise RuntimeError(
                "bharataddress is not installed. Run: pip install bharataddress"
            ) from exc

        # Build kwargs
        parse_kwargs: dict = {}
        if geocode:
            parse_kwargs["geocode"] = True
        if transliterate and has_dev:
            parse_kwargs["transliterate"] = True

        try:
            parsed = ba_parse(raw_address, **parse_kwargs)
        except Exception as exc:
            logger.warning("bharataddress.parse() raised: %s", exc)
            # Return a minimal low-confidence result
            elapsed_ms = (time.perf_counter() - t0) * 1000
            result = Agent1Result(
                building_number=None, building_name=None, landmark=None,
                locality=None, sub_locality=None, city=None,
                district=None, state=None, pincode=None,
                latitude=None, longitude=None,
                raw_confidence=0.0,
                field_confidence={k: 0.0 for k in self._FIELD_PRESENT_CONFIDENCE},
                has_devanagari=has_dev,
                has_landmark_cue=has_cue,
            )
            return result, self._trace(elapsed_ms, ran_ner=False, error=str(exc))

        # -- Build per-field confidence ----------------------------------------
        # Try to get richer signal from bharataddress's validate()
        try:
            validation = ba_validate(parsed)
            val_fields = validation.get("fields", {})
        except Exception:
            val_fields = {}

        fc: dict[str, float] = {}
        for fname, present_conf in self._FIELD_PRESENT_CONFIDENCE.items():
            val = getattr(parsed, fname, None)
            if val is not None:
                # Use validate()'s per-field score if available, else our heuristic
                fc[fname] = float(val_fields.get(fname, present_conf))
            else:
                fc[fname] = 0.0

        # -- Extract geocode fields --------------------------------------------
        lat = getattr(parsed, "latitude", None)
        lon = getattr(parsed, "longitude", None)

        result = Agent1Result(
            building_number  = getattr(parsed, "building_number", None),
            building_name    = getattr(parsed, "building_name", None),
            landmark         = getattr(parsed, "landmark", None),
            locality         = getattr(parsed, "locality", None),
            sub_locality     = getattr(parsed, "sub_locality", None),
            city             = getattr(parsed, "city", None),
            district         = getattr(parsed, "district", None),
            state            = getattr(parsed, "state", None),
            pincode          = getattr(parsed, "pincode", None),
            latitude         = float(lat) if lat is not None else None,
            longitude        = float(lon) if lon is not None else None,
            # bharataddress v0.4 sets digipin directly from parse(geocode=True)
            digipin          = getattr(parsed, "digipin", None),
            raw_confidence   = float(getattr(parsed, "confidence", 0.0)),
            field_confidence = fc,
            has_devanagari   = has_dev,
            has_landmark_cue = has_cue,
            cleaned          = getattr(parsed, "cleaned", None),
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "Agent1 completed in %.1fms: pincode=%s conf=%.2f",
            elapsed_ms, result.pincode, result.raw_confidence,
        )
        return result, self._trace(elapsed_ms)

    @staticmethod
    def _trace(elapsed_ms: float, ran_ner: bool = True, error: str | None = None) -> dict:
        return {
            "agent": "Agent1_DeterministicParser",
            "latency_ms": round(elapsed_ms, 2),
            "approximate_cost_usd": 0.0,
            "ran": True,
            "error": error,
        }
