# Pata (पता) 📍

[![CI](https://github.com/bhargav-ram-lalam/pata/actions/workflows/ci.yml/badge.svg)](https://github.com/bhargav-ram-lalam/pata/actions/workflows/ci.yml)

> **Status: Stage 5 — Full-Stack (AI Engine + Playground + Ops Review Dashboard)**

Pata is an AI-powered address resolution and standardization engine engineered specifically for the complexities of Indian last-mile logistics. Indian addresses are notorious for being unstructured, landmark-centric (e.g., *"behind Hanuman Mandir, opposite yellow water tank"*), colloquial, and frequently plagued by mismatched pincodes, missing house numbers, and mixed-script transliterations. Standard Western geocoders fail on these patterns. Pata combines deterministic postal parsing, fine-grained Named Entity Recognition (NER), spatial landmark validation, and confidence arbitration to resolve messy input into verified, deliverable coordinates and DIGIPIN codes.

---

## Stage 5 Frontend Surfaces

| Surface | Path | Port | Purpose |
|---|---|---|---|
| **Resolution Playground** | `frontend/playground/` | `http://localhost:5173` | Live interactive resolution demo: multi-agent live trace reveal, Leaflet OSM map with landmark connecting lines, DIGIPIN decoder, confidence badges, and one-click benchmark Indian addresses. |
| **Ops Review Dashboard** | `frontend/review-dashboard/` | `http://localhost:5174` | Operator feedback loop: Prometheus telemetry stats header, paginated review queue, draggable map pin repositioning, structured field editing, and instant confirm/correct submission (firing signed webhooks). |

---

## Quick Start (Full Stack Demo)

### 1. Start Backend & Distributed State

```bash
# Option A: Full Production Stack (Postgres + Redis + Pata API)
docker-compose up -d --build
alembic upgrade head

# Option B: Local SQLite Dev (no external services needed)
uvicorn api.main:app --port 8000
```

### 2. Launch Frontend Applications

```bash
# Launch Resolution Playground (Terminal 1)
cd frontend/playground
npm install
npm run dev

# Launch Ops Review Dashboard (Terminal 2)
cd frontend/review-dashboard
npm install
npm run dev
```

Visit **`http://localhost:5173`** for the Resolution Playground and **`http://localhost:5174`** for the Ops Review Dashboard.

---

## API Endpoints Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/v1/resolve` | `POST` | `X-API-Key` | Resolve single address at checkout |
| `/v1/resolve/batch` | `POST` | `X-API-Key` | Batch resolve up to 100 addresses |
| `/v1/review/queue` | `GET` | `X-API-Key` | Paginated review backlog for human verification |
| `/v1/review/{id}/confirm` | `POST` | `X-API-Key` | Mark ML result as confirmed correct |
| `/v1/review/{id}/resolve` | `POST` | `X-API-Key` | Submit human correction (fires HMAC webhook) |
| `/v1/metrics` | `GET` | None | Prometheus telemetry metrics |
| `/v1/health/live` | `GET` | None | Container liveness probe |
| `/v1/health/ready` | `GET` | None | Subsystem & model readiness probe |

See [docs/integration_guide.md](docs/integration_guide.md) for e-commerce checkout integration details.

---

## Architecture & Multi-Agent Pipeline

```
[Raw Address Input]
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ Agent 1: Deterministic Postal Parser (BharatAddress)     │  ~0.2ms
└──────┬───────────────────────────────────────────────────┘
       │ (if landmark cues or low confidence detected)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Agent 2: IndicBERT Address NER (Shiprocket IndicBERT)    │  ~40ms
└──────┬───────────────────────────────────────────────────┘
       │ (spatial landmark candidate lookup)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Agent 3: OSM Overpass Spatial Resolution + Redis Cache   │  ~300ms
└──────┬───────────────────────────────────────────────────┘
       │ (confidence tier arbitration)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Agent 4: Confidence Arbitration & LLM Fallback (Haiku)   │  <1ms / 400ms
└──────┬───────────────────────────────────────────────────┘
       │ (quality audit & DPDP Act compliance)
       ▼
┌──────────────────────────────────────────────────────────┐
│ Agent 5: Self-Check Quality & Verification Audit         │  ~2ms
└──────────────────────────────────────────────────────────┘
```

---

## Running Test Suites

```bash
# Run all API and resilience tests
pytest tests/test_api.py tests/test_resilience.py -v

# Run human-review loop tests
pytest tests/test_review.py -v

# Run pipeline gold test suite
pytest tests/test_pipeline.py -v
```

---

## Regulatory Compliance: India DPDP Act 2023

1. **Mandatory Regional Placement:** All processing infrastructure must be deployed in Indian data regions (e.g. AWS `ap-south-1` Mumbai).
2. **Zero Raw PII Retention:** Long-term database tables contain only structured coordinates, DIGIPIN, and anonymized audit metadata.
3. **Automated 24h Purge Worker:** Short-lived raw address staging records are deleted automatically after 24 hours.
