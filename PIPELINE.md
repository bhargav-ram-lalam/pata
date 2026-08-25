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

## Measured Latency, Cost & Live Observability

In production (Stage 4), latency, agent trigger rates, and LLM token costs are tracked live via Prometheus metrics exposed at `/v1/metrics`.

### Stage 4 Load Test Results (Postgres + Redis, 100 concurrent / 500 requests)

| Metric | Stage 3 (SQLite/in-memory, 30 concurrent) | Stage 4 (Postgres+Redis, 100 concurrent) | Change |
|--------|------------------------------------------|-------------------------------------------|--------|
| **P50** | 45ms | 48ms | +3ms (Redis round-trip overhead) |
| **P95** | 320ms | 340ms | +20ms |
| **P99** | 1,400ms | 1,450ms | +50ms |
| **Throughput** | ~175 req/s | **312 req/s** | +78% from shared cache |
| **Cache hit rate** | Per-instance (cold restarts) | **Shared Redis (warm at scale)** | ✓ |
| **CB state** | Per-instance | **Shared across replicas** | ✓ |

Throughput improvement at 100 concurrent is primarily from Redis shared Overpass cache — no per-replica cache warmup.

### Per-Agent Breakdown

| Agent | When runs | Typical latency | Approximate cost | Live Prometheus Metric |
|-------|-----------|-----------------|-----------------|------------------------|
| A1 — Deterministic Parser | 100% | 0.15–0.5 ms | $0 | `pata_agent_latency_seconds_bucket{agent_name="Agent1_DeterministicParser"}` |
| A2 — IndicBERT NER | Selective (~35–60%) | 35–60 ms (CPU); 10–25 ms (GPU) | $0 (local model) | `pata_agent_triggered_total{agent_name="Agent2_LandmarkNER"}` |
| A3 — OSM Overpass | Selective (~20–40%) | 300–1200 ms (Redis cached: <1ms) | $0 (free API) | `pata_agent_triggered_total{agent_name="Agent3_LandmarkResolution"}` |
| A4 — Arbitration (rules) | 100% | <1 ms | $0 | `pata_requests_total{tier=~"high|low"}` |
| A4 — LLM (MEDIUM tier) | Selective (~5–15%) | 400–1500 ms | ~$0.0001–0.0003 per call | `pata_llm_calls_total`, `pata_llm_tokens_total` |
| A5 — Self-Check | 100% | 1–3 ms | $0 | `pata_needs_human_review_total` |

### Sample PromQL Operational Queries

1. **Average Latency per Agent (last 5 minutes):**
   ```promql
   rate(pata_agent_latency_seconds_sum[5m]) / rate(pata_agent_latency_seconds_count[5m])
   ```

2. **LLM Escalation Rate (% of total traffic hitting Agent 4 LLM):**
   ```promql
   sum(rate(pata_llm_calls_total[1h])) / sum(rate(pata_requests_total[1h])) * 100
   ```

3. **Overpass Circuit Breaker Trip Rate:**
   ```promql
   rate(pata_overpass_circuit_breaker_open_total[1h])
   ```

4. **Human Review Flag Rate by Reason:**
   ```promql
   sum by (reason) (rate(pata_needs_human_review_total[1h]))
   ```

---

## Configuration

All tunable parameters are environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PATA_API_KEYS` | `pata_dev_key` | Comma-separated API keys for `/v1/*` endpoints |
| `PATA_DATABASE_URL` | `sqlite:///./pata.db` | Persistence DB (PostgreSQL / SQLite) |
| `PATA_HIGH_CONF` | `0.80` | Confidence above which LLM is skipped |
| `PATA_MEDIUM_CONF` | `0.50` | Confidence below which address is flagged |
| `PATA_LLM_PROVIDER` | `anthropic` | `anthropic` / `openai` / `google` |
| `PATA_LLM_MODEL` | `claude-haiku-4-5` | Model name within the provider |
| `PATA_LLM_MAX_TOKENS` | `300` | Max tokens for disambiguation prompt |
| `PATA_OVERPASS_CB_THRESHOLD` | `3` | Failure count before tripping Overpass circuit breaker |
| `PATA_REQUEST_TIMEOUT_SEC` | `5.0` | Global pipeline timeout before graceful fallback |

---

## Dependencies

- `bharataddress>=0.4.0` — deterministic parser, phonetic, DIGIPIN, geocoder
- `bharataddress[indic]` — Devanagari transliteration (`indic-transliteration`)
- `bharataddress[fuzzy]` — rapidfuzz for `phonetic.fuzzy_ratio()`
- `transformers>=4.40.0`, `torch>=2.0.0` — IndicBERT NER model
- `fastapi>=0.110.0`, `uvicorn>=0.28.0` — API layer
- `sqlalchemy>=2.0.0` — Persistence & TTL staging
- `prometheus-client>=0.20.0` — Live telemetry
- `pydantic>=2.0.0` — schema contracts

---

---

## Cost-at-Scale Projection

**Measured baseline:** $0.000070 for 15 addresses = **$0.0000047/address**  
**LLM trigger rate:** ~10% of requests reach Agent 4 LLM (MEDIUM tier)  
**LLM cost/call:** ~$0.00015/call (Claude Haiku, ~300 tokens in/out)

| Monthly Order Volume | LLM Calls (10%) | Est. Monthly LLM Cost | Total Infra Cost (est.) |
|---|---|---|---|
| 10,000 orders | ~1,000 | ~$0.15 | ~$0.15 + compute |
| **100,000 orders** | **~10,000** | **~$1.50** | **~$1.50 + compute** |
| **1,000,000 orders** | **~100,000** | **~$15.00** | **~$15.00 + compute** |
| 10,000,000 orders | ~1,000,000 | ~$150.00 | ~$150.00 + compute |

**Key insight:** At 1M orders/month, LLM disambiguation costs **~$15/month** total. Agents 1, 2, 3 and 5 are zero-cost (local models + free OSM API). The entire intelligence stack is 95% free.

---

## Running the API & Tests

```bash
# Run unit & pipeline tests
python tests/test_pipeline.py

# Run API integration tests
pytest tests/test_api.py -v

# Run resilience tests
pytest tests/test_resilience.py -v

# Run review loop tests
cd backend && pytest tests/test_review.py -v

# Run local API service
cd backend && uvicorn api.main:app --port 8000

# Run e-commerce checkout demo
python backend/examples/checkout_integration/simulate_checkout.py

# Export corrections dataset
python backend/scripts/export_corrections.py --output corrections.jsonl
```
