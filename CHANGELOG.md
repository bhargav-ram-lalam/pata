# Changelog — Pata Address Resolution Engine

All notable changes to the Pata codebase are documented in this file.

---

## [0.5.0] — Stage 5: Frontend Surfaces (August 2026)

### Added

**Part A — Surface 1: Resolution Playground (`frontend/playground/`)**
- **Single interactive resolution input** with GPS hint support (`hint_lat`, `hint_lng`).
- **Live Multi-Agent Pipeline Trace visualizer**: progressive staged reveal driven by `pipeline_trace` per-agent latencies for Agents 1–5.
- **Leaflet OpenStreetMap visualizer**: primary geocoded marker, secondary OSM landmark POI marker (from Agent 3), and connecting dashed line.
- **Interactive Medium-Tier Verification UX**: draggable map pin and "Confirm / Update Location" action calling `POST /v1/review/{id}/confirm` and `/resolve`.
- **Prominent Confidence Tier banners**: HIGH (green auto-confirmed), MEDIUM (amber pin verification enabled), LOW (red flagged for ops review).
- **Standardized Address Hierarchy card**: structured key-value grid for building, landmark, road, locality, city, district, state, pincode.
- **DIGIPIN Digital Postal Code card**: copy-to-clipboard, grid breakdown, and India Post / IIT Hyderabad factual explanation tooltip.
- **Audit & Evidence card**: session-only memory display with DPDP 2023 24h retention deadline and JSON inspection.
- **One-click Benchmark Addresses carousel**: 6 preloaded gold Indian addresses from `tests/test_pipeline.py` spanning HIGH, MEDIUM, and LOW tiers.

**Part B — Surface 2: Ops Review Dashboard (`frontend/review-dashboard/`)**
- **Login Gate**: session-only API Key authentication (stored in memory/session only, matching DPDP Act guardrails).
- **Telemetry Stats Header**: live metrics scraped from Prometheus (`pata_review_queue_size`, `pata_reviews_completed_total` confirmed/corrected counts, and `pata_review_turnaround_seconds` SLA averages).
- **Review Queue Table**: paginated, searchable, sortable by lowest-confidence first or timestamp, with reason badges and age indicators.
- **Review Detail & Action Drawer**: Leaflet map with draggable coordinate pin, editable structured fields, reviewer ID/notes inputs, and instant Confirm / Submit Correction action handlers.

**Part C — Shared Infrastructure & Polish**
- Dual Vite + React 19 + TypeScript + Tailwind CSS dark-mode logistics theme.
- Configured default CORS allowlist in `api/main.py`, `.env.example`, and `DEPLOYMENT.md` for ports 5173, 5174, 3000, and 8000.
- Comprehensive error handling for 401 Unauthorized, 429 Rate Limit retry-after headers, and 500/network fallbacks.

---

## [0.4.0] — Stage 4: Scale-Out, Human-Review Loop & E-Commerce Integration (August 2026)

### Added

**Part A — Redis + Postgres Migration (Horizontal Scale Readiness)**
- **Redis-backed rate limiter** (`api/auth.py`): Atomic Lua script (EVALSHA) eliminates TOCTOU race conditions under concurrent replicas. Falls back to in-memory `TokenBucket` when `PATA_REDIS_URL` is unset.
- **Redis-backed Overpass cache** (`resilience/overpass_client.py`): JSON entries stored with `EX` TTL. Cache hits are now shared across all API replicas — no per-instance cold starts.
- **Redis-backed circuit breaker** (`resilience/circuit_breaker.py`): New `RedisCircuitBreaker` subclass stores `CLOSED/OPEN/HALF_OPEN` state in Redis Hash. State transitions use `WATCH/MULTI/EXEC` optimistic locking. Falls back to in-process state on Redis error.
- **PostgreSQL migration via Alembic** (`alembic/`): `alembic.ini`, `env.py`, and initial migration `0001_initial_schema.py` (auto-generated from `persistence/models.Base` — no hand-written SQL). Covers `resolutions`, `raw_address_staging`, and `corrections` tables.
- **Updated `docker-compose.yml`**: Added `postgres:15-alpine` and `redis:7-alpine` services with healthchecks. `pata-api` `depends_on` both with `condition: service_healthy`.
- **`persistence/redis_client.py`**: Lazy singleton with graceful fallback — existing tests and local SQLite dev require no changes.
- Updated `DEPLOYMENT.md`: Postgres + Redis as production topology; SQLite documented as local-dev-only fallback.

**Part B — Human-Review Loop**
- **`review_status` field** on `ResolutionModel`: `pending_review | auto_confirmed | confirmed | corrected | rejected`. Automatically set by `save_resolution()`.
- **`CorrectionModel` table** (`corrections`): Captures original vs corrected lat/lng and parsed fields. This is the fine-tuning feedback dataset.
- **`api/review.py`** — three new endpoints:
  - `GET /v1/review/queue`: Paginated pending_review list, sortable by confidence (lowest first) or timestamp.
  - `POST /v1/review/{request_id}/confirm`: Marks result confirmed-correct, emits Prometheus metric.
  - `POST /v1/review/{request_id}/resolve`: Submits human correction, creates `CorrectionModel` row, fires signed HMAC webhook.
- **Three new Prometheus metrics**: `pata_review_queue_size` (Gauge), `pata_reviews_completed_total` (Counter, label: outcome), `pata_review_turnaround_seconds` (Histogram).
- **`scripts/export_corrections.py`**: CLI to dump corrections table as JSONL for fine-tuning / gold-test-set expansion.
- **`tests/test_review.py`**: 9 integration tests covering the full review lifecycle.

**Part C — E-Commerce Integration**
- **`examples/checkout_integration/simulate_checkout.py`**: Full end-to-end checkout demo showing all three confidence tiers (HIGH auto-confirm, MEDIUM map-pin/review-queue, LOW hold+review). Prints full pipeline trace.
- **`examples/webhook_notification.py`**: HMAC-SHA256 signed webhook delivery. `fire_correction_webhook()` integrates into `api/review.py`. Includes `verify_webhook_signature()` helper for e-commerce receivers.
- **`docs/integration_guide.md`**: Partner integration guide: `/v1/resolve` usage, confidence tier routing pseudocode, latency budget (Stage 4 P50/P95/P99), review queue API, webhook signature verification, cost reference.

**Part D — CI/CD**
- **`.github/workflows/ci.yml`**: Lint (ruff), Alembic migrations, all test suites (including new `test_review.py`), Docker image build — all against Postgres + Redis service containers (not SQLite/in-memory), matching production topology.
- **`.github/workflows/deploy.yml`**: Build + push to GHCR on `main` branch. Documents India-region deployment requirement per DPDP Act.
- CI status badge added to `README.md`.

**Part E — Scalability Evidence**
- **`k8s/deployment.yaml`**: 3 replicas, resource limits from load test (`2 vCPU / 4GB RAM`), liveness/readiness probes, non-root security context, topology spread for HA.
- **`k8s/service.yaml`**: ClusterIP service, port 80 → 8000, Prometheus annotations.
- **`k8s/hpa.yaml`**: HPA min 2 / max 10 replicas, CPU target 70%, aggressive scale-up (4 pods/60s for sale events), conservative scale-down (5-minute stabilisation).
- **Updated `PIPELINE.md`**: Stage 4 load test results (100 concurrent / 500 requests, Postgres+Redis), cost-at-scale projection (100K orders → ~$1.50/month LLM cost, 1M orders → ~$15/month).

### Changed
- `api/main.py`: Version bumped `0.3.0` → `0.4.0`. Review router included.
- `api/schemas.py`: Added `ReviewQueueItem`, `ReviewQueueResponse`, `ConfirmRequest`, `CorrectRequest`.
- `observability/metrics.py`: Added three review loop metrics.
- `persistence/models.py`: Added `review_status` to `ResolutionModel`; added `CorrectionModel`.
- `persistence/repository.py`: `save_resolution()` now sets `review_status`; added `get_review_queue()`, `confirm_resolution()`, `correct_resolution()`, `get_corrections_for_export()`.
- `requirements.txt` / `pyproject.toml`: Added `redis>=5.0.0`, `psycopg2-binary>=2.9.9`, `alembic>=1.13.0`.
- `.env.example`: Added `PATA_REDIS_URL`, `POSTGRES_PASSWORD`, `PATA_WEBHOOK_URL`, `PATA_WEBHOOK_SECRET`.

---

## [0.3.0] — Stage 3: Production Hardening (August 2026)

### Added
- **FastAPI Application Layer (`api/`):**
  - `POST /v1/resolve`: Single address resolution endpoint with GPS hint support and global request timeout guardrails.
  - `POST /v1/resolve/batch`: Concurrent batch processing (up to 100 addresses) with bounded concurrency (`asyncio.Semaphore(10)`) and per-item error isolation.
  - `GET /v1/resolve/{request_id}`: Query past non-PII resolution records without re-parsing.
  - `GET /v1/health`, `GET /v1/health/live`, `GET /v1/health/ready`: Subsystem health diagnostics and container orchestration probes.
  - `GET /v1/metrics`: Prometheus metrics exposition format.
  - `X-Request-ID` correlation ID middleware tracking requests across all agent log lines and trace metadata.
- **Persistence & DPDP Act Compliance (`persistence/`):**
  - Permanent `resolutions` table holding non-PII structured results, DIGIPIN, coordinates, and audit evidence.
  - Short-lived `raw_address_staging` table with indexed `purge_after` timestamps.
  - Background async purge worker and standalone CLI (`python -m persistence.purge_job`) running automated hourly raw address deletions.
- **Resilience & Dependency Circuit Breakers (`resilience/`):**
  - Generic `CircuitBreaker` pattern (`CLOSED`, `OPEN`, `HALF-OPEN`) protecting external API calls.
  - Hardened Overpass client with exponential retry backoff, circuit breaking, and in-memory LRU TTL caching.
  - Agent 4 LLM fallback to LOW confidence tier with explicit audit evidence when remote providers fail.
  - Prompt injection defense enclosing user address inputs within strict `<raw_address_data>` boundaries.
- **Observability (`observability/`):**
  - Prometheus collectors: `pata_requests_total`, `pata_agent_triggered_total`, `pata_agent_latency_seconds`, `pata_llm_calls_total`, `pata_llm_tokens_total`, `pata_overpass_circuit_breaker_open_total`, `pata_needs_human_review_total`.
  - Structured JSON-lines logging with automatic PII redaction above DEBUG level.
- **Deployment Assets:**
  - Multi-stage `Dockerfile` with non-root security user (`patauser`), `docker-compose.yml`, `.env.example`, and comprehensive `DEPLOYMENT.md`.
- **Testing Suites (`tests/`):**
  - `tests/test_api.py`: Full API integration suite covering single, batch, auth, rate limiting, health, and persistence.
  - `tests/test_resilience.py`: Mocked failure tests for Overpass circuit breaking, LLM fallback, global timeout, and prompt injection defense.
  - `tests/load_test.py`: Asynchronous concurrent load generator reporting p50, p95, and p99 latencies across tiers.

---

## [0.2.0] — Stage 2: 5-Agent Pipeline (August 2026)

### Added
- Working 5-agent pipeline architecture:
  - Agent 1: Deterministic parser (`bharataddress.parse()`).
  - Agent 2: IndicBERT address NER (`shiprocket-ai/open-indicbert-indian-address-ner`).
  - Agent 3: OSM landmark resolution via Overpass API.
  - Agent 4: Confidence arbitration and selective LLM escalation for MEDIUM tier.
  - Agent 5: Self-check validation and DIGIPIN generation.
- 15-case benchmark test suite (`tests/test_pipeline.py`).

---

## [0.1.0] — Stage 1: Scaffolding & Foundation Validation (August 2026)

### Added
- Initial project scaffolding (`pyproject.toml`, `requirements.txt`, `.gitignore`, `README.md`, `src/pata/`).
- Foundation library validation scripts (`scripts/validate_bharataddress.py`, `scripts/validate_indicbert.py`).
- Empirical findings and merge-policy report (`docs/foundation_validation.md`).
