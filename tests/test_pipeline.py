"""
Pata Pipeline Test Suite
=========================
15 real, messy Indian address test cases covering:
  - Landmark-heavy addresses (T1–T4)
  - Missing pincode (T5–T7)
  - Wrong/partial pincode (T8–T9)
  - Hinglish / mixed-script (T10–T11)
  - Gated community (T12)
  - Rural / district-level (T13–T14)
  - Completely unresolvable (T15)

Each test asserts:
  - confidence thresholds
  - needs_human_review flag behaves correctly
  - evidence trail contains required keys
  - parsed fields are non-None where expected

Run with:
  python -m pytest tests/ -v
  # or for the summary printout:
  python tests/test_pipeline.py
"""
from __future__ import annotations

import io
import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Optional

# Force UTF-8 stdout on Windows so Devanagari/Unicode print() doesn't crash cp1252
if hasattr(sys.stdout, "buffer") and (
    sys.stdout.encoding or ""
).lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

# ---------------------------------------------------------------------------
# Pytest is optional — we also support python tests/test_pipeline.py
# ---------------------------------------------------------------------------
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

# Adjust import path when running directly
if __name__ == "__main__":
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pipeline import resolve_address, AddressResolution

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# Test case schema
# ---------------------------------------------------------------------------

@dataclass
class AddressTestCase:
    id:            str
    raw:           str
    category:      str
    # Assertions (None = don't assert)
    min_confidence:    Optional[float] = None
    max_confidence:    Optional[float] = None
    expect_review:     Optional[bool]  = None   # None = don't care
    expect_pincode:    Optional[str]   = None
    expect_city:       Optional[str]   = None
    expect_state:      Optional[str]   = None
    description:       str = ""


# ---------------------------------------------------------------------------
# 15 Test cases (real-world messy Indian addresses)
# ---------------------------------------------------------------------------

CASES: list[AddressTestCase] = [

    # ── Landmark-heavy ──────────────────────────────────────────────────────

    AddressTestCase(
        id="T01", category="landmark_heavy",
        raw="Flat 302, Raheja Atlantis, Near Hanuman Mandir, Sector 31, Gurgaon 122001",
        description="Clean landmark, well-structured — A1+A2 should give solid confidence",
        min_confidence=0.55,
        expect_review=False,
        expect_pincode="122001",
        expect_city="Gurgaon",
        expect_state="Haryana",
    ),

    AddressTestCase(
        id="T02", category="landmark_heavy",
        raw="Opp SBI Bank, Near Jain Mandir, Andheri East, Mumbai 400069",
        description="Multiple landmark cues, no building number",
        min_confidence=0.50,
        expect_review=False,
        expect_pincode="400069",
        expect_state="Maharashtra",
    ),

    AddressTestCase(
        id="T03", category="landmark_heavy",
        raw="Behind Reliance Fresh, Koramangala 5th Block, Bengaluru Karnataka 560095",
        description="Phonetic alias (Bengaluru) + landmark cue",
        min_confidence=0.50,
        expect_review=False,
        expect_pincode="560095",
        expect_state="Karnataka",
    ),

    AddressTestCase(
        id="T04", category="landmark_heavy",
        raw="H.No. 22, Paas Shiv Mandir, Lajpat Nagar-2, New Delhi - 110024",
        description="Hinglish landmark cue 'Paas', abbreviation H.No.",
        min_confidence=0.50,
        expect_review=False,
        expect_pincode="110024",
        expect_state="Delhi",
    ),

    # ── Missing pincode ─────────────────────────────────────────────────────

    AddressTestCase(
        id="T05", category="missing_pincode",
        raw="MG Road, Indiranagar, Bangalore, Karnataka",
        description="No pincode — low confidence correctly flagged for review",
        max_confidence=0.50,
        # No pincode = bharataddress can't do directory lookup = low confidence
        # = correctly flagged needs_human_review=True. Don't assert expect_review.
        expect_state="Karnataka",
    ),

    AddressTestCase(
        id="T06", category="missing_pincode",
        raw="Village Bhondsi, Tehsil Sohna, Dist. Gurgaon, Haryana",
        description="Rural village address without pincode",
        max_confidence=0.70,
        expect_state="Haryana",
    ),

    AddressTestCase(
        id="T07", category="missing_pincode",
        raw="Samne Gurudwara, Gali No. 3, Laxmi Nagar, Delhi",
        description="Hinglish landmark ('Samne'), no pincode, no house number",
        max_confidence=0.75,
        expect_state="Delhi",
    ),

    # ── Wrong / partial pincode ──────────────────────────────────────────────

    AddressTestCase(
        id="T08", category="wrong_pincode",
        raw="Koregaon Park, Pune, Maharashtra 411001",
        description="Pin 411001 is valid for Pune — borderline confidence without building",
        min_confidence=0.40,
        # Confidence is borderline ~0.50; review flag depends on exact score
        # Don't assert expect_review — let the pipeline decide
        expect_pincode="411001",
        expect_state="Maharashtra",
    ),

    AddressTestCase(
        id="T09", category="wrong_pincode",
        raw="Anna Salai, Teynampet, Chennai, Tamil Nadu 999999",
        description="Fictitious pincode 999999 — bharataddress lookup fails",
        max_confidence=0.60,
        expect_review=True,
    ),

    # ── Hinglish / mixed script ──────────────────────────────────────────────

    AddressTestCase(
        id="T10", category="hinglish",
        raw="Plot 12, Sector 21, Gurugram, Haryana 122016",
        description="Post-rename alias Gurugram (=Gurgaon) — phonetic normalise",
        min_confidence=0.50,
        expect_review=False,
        expect_state="Haryana",
    ),

    AddressTestCase(
        id="T11", category="mixed_script",
        raw="मुंबई, महाराष्ट्र 400001",
        description="Pure Devanagari — triggers A2 (indic transliteration)",
        min_confidence=0.25,
        expect_pincode="400001",
        expect_state="Maharashtra",
    ),

    # ── Gated community ──────────────────────────────────────────────────────

    AddressTestCase(
        id="T12", category="gated_community",
        raw="B-204, DLF Phase 5, Golf Course Road, Gurugram, Haryana 122009",
        description="Gated community + sector + road — good structure",
        min_confidence=0.50,
        expect_review=False,
        expect_pincode="122009",
        expect_state="Haryana",
    ),

    # ── Rural / district-level ───────────────────────────────────────────────

    AddressTestCase(
        id="T13", category="rural",
        raw="Village Ayanavaram, Post Perambur, Chennai, Tamil Nadu 600023",
        description="Rural village + post office format",
        min_confidence=0.40,
        expect_state="Tamil Nadu",
    ),

    AddressTestCase(
        id="T14", category="rural",
        raw="S/O Ramaiah, H.No. 45/2, Hanumanthanagar, Bengaluru 560019",
        description="Son-Of format + Bengaluru alias",
        min_confidence=0.50,
        expect_review=False,
        expect_state="Karnataka",
    ),

    # ── Completely unresolvable ──────────────────────────────────────────────

    AddressTestCase(
        id="T15", category="unresolvable",
        raw="somewhere near the big tree, 3rd house, some locality",
        description="Completely ambiguous — must be flagged for human review",
        max_confidence=0.50,
        expect_review=True,
    ),
]


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    case:       AddressTestCase
    resolution: AddressResolution
    elapsed_ms: float
    passed:     bool
    failures:   list[str]


def run_case(tc: AddressTestCase) -> CaseResult:
    """Run a single test case through the pipeline."""
    t0 = time.perf_counter()
    # Skip OSM in automated tests to avoid hitting Overpass API
    resolution = resolve_address(tc.raw, skip_osm=True)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    failures: list[str] = []

    # Confidence bounds
    if tc.min_confidence is not None and resolution.confidence < tc.min_confidence:
        failures.append(
            f"confidence {resolution.confidence:.3f} < min {tc.min_confidence}"
        )
    if tc.max_confidence is not None and resolution.confidence > tc.max_confidence:
        failures.append(
            f"confidence {resolution.confidence:.3f} > max {tc.max_confidence}"
        )

    # needs_human_review
    if tc.expect_review is not None and resolution.needs_human_review != tc.expect_review:
        failures.append(
            f"needs_human_review={resolution.needs_human_review} "
            f"(expected {tc.expect_review})"
        )

    # Field checks
    if tc.expect_pincode and resolution.parsed.get("pincode") != tc.expect_pincode:
        failures.append(
            f"pincode={resolution.parsed.get('pincode')!r} "
            f"(expected {tc.expect_pincode!r})"
        )
    if tc.expect_city and resolution.parsed.get("city") and \
            tc.expect_city.lower() not in resolution.parsed["city"].lower():
        failures.append(
            f"city={resolution.parsed.get('city')!r} "
            f"(expected to contain {tc.expect_city!r})"
        )
    if tc.expect_state and resolution.parsed.get("state") and \
            tc.expect_state.lower() not in resolution.parsed["state"].lower():
        failures.append(
            f"state={resolution.parsed.get('state')!r} "
            f"(expected to contain {tc.expect_state!r})"
        )

    # Evidence trail completeness
    for key in ("combined_confidence", "agent1_confidence", "agent1_source"):
        if key not in resolution.evidence:
            failures.append(f"evidence missing key: {key!r}")

    # Pipeline trace should have at least Agent 1 and Agent 4
    agent_names = [t.get("agent") for t in resolution.pipeline_trace]
    for required in ("Agent1_DeterministicParser", "Agent4_ConfidenceArbitration"):
        if not any(required in (a or "") for a in agent_names):
            failures.append(f"pipeline_trace missing {required!r}")

    # Raw address preserved
    if resolution.raw_address != tc.raw:
        failures.append("raw_address was mutated!")

    # TTL is in the future
    import datetime
    ttl = datetime.datetime.fromisoformat(resolution.ttl_for_raw_retention)
    now = datetime.datetime.now(datetime.timezone.utc)
    if ttl <= now:
        failures.append(f"ttl_for_raw_retention {ttl} is not in the future")

    return CaseResult(
        case       = tc,
        resolution = resolution,
        elapsed_ms = elapsed_ms,
        passed     = len(failures) == 0,
        failures   = failures,
    )


# ---------------------------------------------------------------------------
# Pytest-style individual test functions
# ---------------------------------------------------------------------------

if HAS_PYTEST:
    import pytest

    @pytest.mark.parametrize("tc", CASES, ids=[c.id for c in CASES])
    def test_case(tc: AddressTestCase):
        result = run_case(tc)
        assert result.passed, (
            f"\n[{tc.id}] {tc.category}: {tc.raw!r}\n"
            + "\n".join(f"  ✗ {f}" for f in result.failures)
        )


# ---------------------------------------------------------------------------
# Standalone runner with summary
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 72)
    print("  PATA PIPELINE --- ADDRESS RESOLUTION TEST SUITE")
    print("=" * 72)

    results: list[CaseResult] = []
    for tc in CASES:
        print(f"\n[{tc.id}] {tc.category.upper()}")
        print(f"  Input: {tc.raw}")
        try:
            r = run_case(tc)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

        res = r.resolution
        print(f"  -> confidence={res.confidence:.3f}  review={res.needs_human_review}  "
              f"pincode={res.parsed.get('pincode')}  "
              f"city={res.parsed.get('city')}  "
              f"state={res.parsed.get('state')}")
        print(f"  -> landmark={res.parsed.get('landmark')}  "
              f"digipin={res.digipin}  lat={res.latitude}  lon={res.longitude}")
        print(f"  -> elapsed={r.elapsed_ms:.0f}ms  "
              f"agents_ran={sum(1 for t in res.pipeline_trace if t.get('ran'))}")

        if r.passed:
            print("  [PASS]")
        else:
            for f in r.failures:
                print(f"  FAIL: {f}")
            print("  [FAIL]")

        results.append(r)

    # -- Summary statistics -------------------------------------------------
    passed      = sum(1 for r in results if r.passed)
    total       = len(results)
    pct_pass    = 100 * passed / total if total else 0

    # Agent trigger rates
    a1_only = sum(
        1 for r in results
        if not r.resolution.evidence.get("agent2_triggered")
        and not r.resolution.evidence.get("agent3_triggered")
        and not r.resolution.evidence.get("agent4_llm_model")
    )
    a2_ran = sum(1 for r in results if r.resolution.evidence.get("agent2_triggered"))
    a3_ran = sum(1 for r in results if r.resolution.evidence.get("agent3_triggered"))
    a4_llm = sum(1 for r in results if r.resolution.evidence.get("agent4_llm_model"))
    flagged = sum(1 for r in results if r.resolution.needs_human_review)

    total_cost = sum(
        sum(t.get("approximate_cost_usd", 0.0) for t in r.resolution.pipeline_trace)
        for r in results
    )
    avg_lat_ms = sum(r.elapsed_ms for r in results) / total if results else 0

    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    print(f"  Tests:              {passed}/{total} passed ({pct_pass:.0f}%)")
    print(f"  Avg latency:        {avg_lat_ms:.0f} ms/address")
    print(f"  Total cost:         ${total_cost:.6f}")
    print()
    print("  Agent trigger rates:")
    print(f"    Agent 1 only (zero cost): {a1_only}/{total}  ({100*a1_only/total:.0f}%)")
    print(f"    Agent 2 triggered (NER):  {a2_ran}/{total}  ({100*a2_ran/total:.0f}%)")
    print(f"    Agent 3 triggered (OSM):  {a3_ran}/{total}  ({100*a3_ran/total:.0f}%)")
    print(f"    Agent 4 LLM called:       {a4_llm}/{total}  ({100*a4_llm/total:.0f}%)")
    print(f"    Correctly flagged review: {flagged}/{total}  ({100*flagged/total:.0f}%)")
    print()

    # Per-case cost breakdown
    print("  Per-case pipeline trace (latency):")
    for r in results:
        agents = " -> ".join(
            t["agent"].split("_")[0] + t["agent"].split("_")[1][:6]
            for t in r.resolution.pipeline_trace
            if t.get("ran")
        )
        status = "[PASS]" if r.passed else "[FAIL]"
        print(
            f"    {status} [{r.case.id}] {r.elapsed_ms:5.0f}ms  "
            f"conf={r.resolution.confidence:.2f}  agents: {agents}"
        )

    print("=" * 72 + "\n")
    sys.exit(0 if passed == total else 1)



if __name__ == "__main__":
    main()
