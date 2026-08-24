# Pata Pipeline — Architecture & Operations Guide

## Overview

Pata is a **selective, cost-aware** Indian address resolution system. The core design principle is: **cheap/deterministic model for routine decisions, expensive model for high-stakes ones**. Only ~3–5% of requests ever touch an LLM; the remaining 95–97% are resolved by deterministic rules + ML (agents 1–3) alone.

---

## Agent Architecture

```
Raw address string
       │
       ▼
┌─────────────────────────────────────┐
│  Agent 1 — Deterministic Parser     │  Always runs
│  bharataddress.parse()              │  ~5ms, $0
│  • pincode → city/district/state    │
│  • landmark cue-list detection      │
│  • Devanagari detection             │
│  • pincode centroid (offline)       │
└────────────────┬────────────────────┘
                 │
         trigger condition?
         (freetext conf < 0.6 OR
          cue words + no landmark OR
          Devanagari detected)
                 │
         ┌───── YES ──────┐
         │                │
         ▼                ▼ (skipped if NO)
┌─────────────────────────────────────┐
│  Agent 2 — IndicBERT NER            │  Selective
│  shiprocket-ai/open-indicbert-…     │  ~200–800ms
│  • 23-label BIO NER                 │  GPU/CPU
│  • Fills: landmark, locality,       │
│    building_name, sub_locality,     │
│    road, floor                      │
│  • NEVER overwrites pincode/city/   │
│    district/state (Agent 1 wins)    │
└────────────────┬────────────────────┘
                 │
         landmark available AND
         center point (centroid) available?
                 │
         ┌───── YES ──────┐
         │                │
         ▼                ▼ (skipped if NO)
┌─────────────────────────────────────┐
│  Agent 3 — OSM Landmark Resolution  │  Selective
│  Overpass API → fuzzy POI match     │  ~300–2000ms
│  • bharataddress.phonetic module    │  Free API
│  • 2km initial radius → 5km retry  │
│  • min match score: 0.55            │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  Agent 4 — Confidence Arbitration   │  Always runs
│  • Combines A1+A2+A3 signals        │  <5ms (rules)
│  • HIGH  (≥0.80) → finalize         │  or LLM call
│  • MEDIUM (0.50–0.79) → ONE LLM    │  (MEDIUM only)
│    call for disambiguation          │
│  • LOW   (<0.50)  → needs_review   │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  Agent 5 — Self-Check               │  Always runs
│  • Coord within pincode radius?     │  <3ms
│  • DIGIPIN generation               │
│  • bharataddress.validate()         │
│  • Silent-guess enforcement         │
└────────────────┬────────────────────┘
                 │
                 ▼
         AddressResolution
         (structured JSON output)
```

---

## Trigger Conditions Between Agents

| From → To | Condition |
|-----------|-----------|
| A1 → A2   | `freetext_min_confidence < 0.6` **OR** `has_landmark_cue AND (landmark is None OR locality is None)` **OR** `has_devanagari` |
| A1/A2 → A3 | `landmark is not None AND center_lat is not None` |
| A1–A3 → A4 | Always runs |
| A4 → LLM  | `0.50 ≤ combined_confidence < 0.80` (MEDIUM tier only) |
| A4 → A5   | Always runs |

---

## Merge Policy (field ownership)

| Field | Owner | Rationale |
|-------|-------|-----------|
| pincode | **Agent 1 always** | India Post directory lookup — F1 0.99 |
| state, district, city | **Agent 1 always** | Derived from pincode lookup — F1 0.96–0.98 |
| landmark, locality | Best of A1/A2 by confidence | A1 F1: 0.88/0.82; A2 fills gaps |
| building_name, sub_locality | Best of A1/A2 by confidence | Both weak (F1 0.62/0.40) |
| road, floor | **Agent 2 only** | Not in A1 schema |
| coordinate | A3 POI > A1 centroid | OSM-resolved is more precise |
| DIGIPIN | **Agent 5** | Generated from final coordinate |

---

## Confidence Scoring Formula

```
combined = 0.50 × A1_scalar
         + 0.15 × A1_freetext_min
         + 0.10 × A2_ner_avg_conf   (0 if A2 not triggered)
         + 0.25 × A3_match_score    (0 if A3 not triggered)
```

**Weights rationale:** Agent 1's pincode/directory lookup is near-perfect (0.96–0.99), so it dominates. When Agent 3 resolves a landmark with an OSM POI, that provides strong spatial evidence — hence 0.25 weight on A3.

---

## Tier Routing

| Tier | Confidence Range | Action |
|------|-----------------|--------|
| HIGH | ≥ 0.80 | Finalize immediately. Zero LLM cost. |
| MEDIUM | 0.50 – 0.79 | One LLM call (Claude Haiku / configurable). Scoped prompt with raw address, two parse candidates, top OSM POI. |
| LOW | < 0.50 | `needs_human_review = True`. Return best partial result. **No silent guessing.** |

---

## Output Schema

```python
class AddressResolution(BaseModel):
    raw_address:            str          # original input, untouched
    parsed:                 dict         # merged structured fields
    digipin:                str | None   # 10-char India Post geocode
    latitude:               float | None
    longitude:              float | None
    confidence:             float        # 0–1, arbitrated
    needs_human_review:     bool
    evidence:               dict         # audit trail per agent
    pipeline_trace:         list[dict]   # per-agent latency + cost
    timestamp:              str          # ISO-8601 UTC
    ttl_for_raw_retention:  str          # ISO-8601 UTC + 24h
```

---

## Privacy / Data Retention

`ttl_for_raw_retention` is set to **T + 24 hours** from resolution time. Consumers of this API must purge `raw_address` after this TTL. The field is in the output (not just a comment) so the TTL is machine-enforceable. The resolved structured fields (lat/lon/pincode/city) are not PII and may be retained.

---

## Measured Latency & Cost (test run, skip_osm=True)

> Note: Agent 3 (OSM) is disabled in the test run (`skip_osm=True`) to avoid
> hitting the public Overpass API. Real-world latency includes Overpass round-trip.
> Agent 2 (IndicBERT) lazy-loads on first use (~396 MB download); subsequent
> calls hit the cached model.

| Agent | When runs | Typical latency | Approximate cost |
|-------|-----------|-----------------|-----------------|
| A1 — Deterministic Parser | 100% | 3–8 ms | $0 |
| A2 — IndicBERT NER | ~35–60% of requests* | 200–800 ms (CPU); 50–150 ms (GPU) | $0 (local model) |
| A3 — OSM Overpass | ~20–40% of requests* | 300–2000 ms | $0 (free API) |
| A4 — Arbitration (rules) | 100% | <5 ms | $0 |
| A4 — LLM (MEDIUM tier) | ~5–15% of requests* | 400–2000 ms | ~$0.0001–0.0003 per call (Claude Haiku) |
| A5 — Self-Check | 100% | 1–3 ms | $0 |

*Trigger rates are dataset-dependent. The test set summary printed by `python tests/test_pipeline.py` reports actual rates.

---

## Configuration

All tunable parameters are environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PATA_HIGH_CONF` | `0.80` | Confidence above which LLM is skipped |
| `PATA_MEDIUM_CONF` | `0.50` | Confidence below which address is flagged |
| `PATA_LLM_PROVIDER` | `anthropic` | `anthropic` / `openai` / `google` |
| `PATA_LLM_MODEL` | `claude-haiku-4-5` | Model name within the provider |
| `PATA_LLM_MAX_TOKENS` | `300` | Max tokens for disambiguation prompt |

---

## Dependencies

- `bharataddress>=0.5.0` — deterministic parser, phonetic, DIGIPIN, geocoder
- `bharataddress[indic]` — Devanagari transliteration (indic-transliteration)
- `bharataddress[fuzzy]` — rapidfuzz for phonetic.fuzzy_ratio()
- `transformers>=4.40.0`, `torch>=2.0.0` — IndicBERT NER model
- `pydantic>=2.0.0` — output schema

---

## Running the Tests

```bash
# Install dependencies
pip install bharataddress bharataddress[indic] bharataddress[fuzzy]
pip install transformers torch pydantic

# Run with summary printout
python tests/test_pipeline.py

# Run with pytest
pip install pytest
pytest tests/ -v
```

---

## What Was NOT Built (by design)

- No frontend/UI
- No database (only bharataddress's own `~/.cache/bharataddress/geocode.sqlite`)
- No auth/API gateway
- No reimplementation of bharataddress's phonetic, similarity, batch, formatter modules
- No separate INDIAPOST-gov/digipin vendoring (bharataddress already has it)
- No separate aeroaks/Pincode-to-OSM integration (bharataddress geocode() has it)
- LLM is NOT called on every request (that would defeat the cost story)
