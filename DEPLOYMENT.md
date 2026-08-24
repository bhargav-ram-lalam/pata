# Pata Deployment & Operations Guide

**Service Version:** `0.4.0` (Stage 4 — Scale-Out & Human-Review Loop)  
**Target Environment:** Containerized Microservice (Docker / Kubernetes)

---

## 1. Regulatory & Compliance: India Data Residency (DPDP Act 2023)

Under the **Digital Personal Data Protection Act (DPDP Act 2023)**, address strings and recipient locations constitute identifiable personal data. Pata implements structural privacy guardrails:

> [!IMPORTANT]
> **Mandatory Regional Placement:**  
> All computing infrastructure, container clusters, databases, and LLM inference endpoints processing Indian customer addresses **MUST** be deployed within Indian geographic boundaries (e.g., AWS `ap-south-1` Mumbai / `ap-south-2` Hyderabad, GCP `asia-south1` Mumbai / `asia-south2` Delhi, or Azure Central India).

### Privacy Architecture & Retention Safeguards
1. **Zero Raw PII in Long-Term Storage:**  
   The primary `resolutions` database table stores only anonymized/structured geographic data (pincode, revenue city, state, coordinates, DIGIPIN, and confidence evidence). It contains **no** recipient names, house numbers, or raw address strings.
2. **Automated 24-Hour TTL Purge:**  
   Raw address strings are staged strictly in `raw_address_staging` with an indexed `purge_after = created_at + 24h` timestamp. An automated background worker deletes expired records every hour.
3. **Structured Logging Filter:**  
   The logging subsystem automatically redacts raw address fields at `INFO` level and above (`[REDACTED_PII]`).

---

## 2. Production Topology (Stage 4)

```
                    ┌──────────────────────────────────────────┐
                    │  Load Balancer (ap-south-1 Mumbai)       │
                    └────────────────┬─────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
         ┌────▼────┐           ┌─────▼───┐           ┌─────▼───┐
         │ Pata API│           │Pata API │           │Pata API │  (HPA: 2-10 pods)
         │ pod 1   │           │ pod 2   │           │ pod N   │
         └────┬────┘           └────┬────┘           └────┬────┘
              └──────────┬──────────┘──────────┬──────────┘
                         │                     │
              ┌──────────▼──────────┐ ┌────────▼──────────┐
              │    PostgreSQL 15    │ │     Redis 7        │
              │  (Primary + Rep.)  │ │  Rate Limiter      │
              │  resolutions,      │ │  Overpass Cache    │
              │  corrections,      │ │  Circuit Breaker   │
              │  raw_address_stg   │ │  State             │
              └────────────────────┘ └───────────────────-┘
```

> [!IMPORTANT]
> **Stage 4 Production Stack:** PostgreSQL + Redis are now required for multi-instance deployments. SQLite and in-memory state are **local-dev only**.

---

## 3. Environment Configuration Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `PATA_API_KEYS` | `pata_dev_key,test_api_key_stage3` | Comma-separated list of valid API keys |
| `PATA_DATABASE_URL` | `sqlite:///./pata.db` | **Production:** `postgresql+psycopg2://user:pass@host:5432/pata` |
| `PATA_REDIS_URL` | *(None)* | **Production:** `redis://redis-host:6379/0` — enables distributed rate limiter, Overpass cache, circuit breaker state |
| `PATA_PURGE_INTERVAL_SEC` | `3600` | Set to `0` in multi-replica to use external CronJob instead |
| `PATA_REQUEST_TIMEOUT_SEC` | `5.0` | Global API request timeout before graceful degradation |
| `PATA_HIGH_CONF` | `0.80` | High confidence cutoff for skipping Agent 4 LLM |
| `PATA_MEDIUM_CONF` | `0.50` | Medium confidence lower bound for triggering Agent 4 LLM |
| `PATA_LLM_PROVIDER` | `anthropic` | LLM provider: `anthropic`, `openai`, or `google` |
| `PATA_LLM_MODEL` | `claude-haiku-4-5` | Specific model within provider |
| `ANTHROPIC_API_KEY` | *(None)* | API secret for Anthropic Claude |
| `PATA_OVERPASS_URL` | `https://overpass-api.de/...` | OpenStreetMap Overpass interpreter endpoint |
| `PATA_OVERPASS_CB_THRESHOLD` | `3` | Consecutive failures before tripping circuit breaker |
| `PATA_OVERPASS_CB_COOLDOWN_SEC` | `60.0` | Duration circuit breaker stays OPEN before HALF-OPEN |
| `PATA_RATE_LIMIT_RPS` | `20.0` | Token bucket replenishment rate per API key (Redis-backed) |
| `PATA_RATE_LIMIT_BURST` | `40.0` | Maximum bucket capacity per API key |
| `PATA_WEBHOOK_URL` | *(None)* | URL for correction webhook POST notifications |
| `PATA_WEBHOOK_SECRET` | `changeme_in_production` | HMAC-SHA256 shared secret for webhook signatures |
| `PATA_CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins |

### Local Dev Fallback (SQLite-only, no Redis)

Set only these two variables to run without external services:

```bash
PATA_DATABASE_URL=sqlite:///./pata.db
# Omit PATA_REDIS_URL entirely
```

Rate limiter, Overpass cache, and circuit breaker automatically fall back to in-memory implementations. **Not suitable for multi-instance deployments.**

---

## 4. Running with Docker Compose (Full Stack)

```bash
# Copy and customize environment variables
cp .env.example .env

# Start Postgres + Redis + Pata API
docker-compose up -d --build

# Run Alembic migrations (first-time or after schema updates)
docker-compose exec pata-api alembic upgrade head

# View real-time logs
docker-compose logs -f pata-api
```

### Verify Endpoints

```bash
# Liveness probe (unauthenticated)
curl -i http://localhost:8000/v1/health/live

# Readiness probe (unauthenticated)
curl -i http://localhost:8000/v1/health/ready

# Single address resolution (authenticated)
curl -X POST http://localhost:8000/v1/resolve \
  -H "X-API-Key: pata_dev_key" \
  -H "Content-Type: application/json" \
  -d '{"address": "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru 560076"}'

# Human review queue
curl -H "X-API-Key: pata_dev_key" http://localhost:8000/v1/review/queue

# Prometheus metrics
curl http://localhost:8000/v1/metrics
```

---

## 5. Database Migrations (Alembic)

```bash
# Apply all migrations to Postgres
alembic upgrade head

# Generate a new migration after model changes
alembic revision --autogenerate -m "description_of_change"

# Check current migration version
alembic current
```

> [!NOTE]
> `init_db()` (SQLAlchemy `create_all`) is kept for local SQLite dev only.  
> For Postgres production, always use `alembic upgrade head`.

---

## 6. TTL Purge Worker Architecture

### Option A: In-Process Async Worker (Single Replica / Local Dev)
The API service runs `PurgeWorker` inside the FastAPI `lifespan` event loop. Runs every `PATA_PURGE_INTERVAL_SEC` seconds.

### Option B: Standalone Kubernetes CronJob (Multi-Replica — Recommended)
Set `PATA_PURGE_INTERVAL_SEC=0` to disable the in-process worker, then deploy:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pata-ttl-purge
spec:
  schedule: "0 * * * *" # Hourly
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: purge
            image: pata-api:0.4.0
            command: ["python", "-m", "persistence.purge_job"]
            envFrom:
            - secretRef:
                name: pata-secrets
          restartPolicy: OnFailure
```

---

## 7. Horizontal Scaling & Sizing Guidelines

- **Compute / RAM:** `2 vCPUs` and `4 GB RAM` per replica (IndicBERT ~125MB; rest is OS + Python)
- **Postgres:** Minimum 2-node primary-replica setup; connection pooling via `pool_size=10, max_overflow=20`
- **Redis:** Single-node sufficient for rate limiting; use Redis Sentinel or Cluster for HA
- **HPA:** See `k8s/hpa.yaml` — min 2 replicas, max 10, CPU target 70%

---

## 8. Webhook Configuration (E-Commerce Integration)

Set `PATA_WEBHOOK_URL` and `PATA_WEBHOOK_SECRET` to receive signed correction events:

```bash
PATA_WEBHOOK_URL=https://your-ecommerce-backend.example.com/pata/webhook
PATA_WEBHOOK_SECRET=your_256_bit_secret_here
```

Webhook payload is signed with HMAC-SHA256. See [docs/integration_guide.md](docs/integration_guide.md) for signature verification code.
