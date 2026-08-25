# Pata — Architecture Diagrams

Three focused diagrams. Each is readable at slide dimensions (16:9).  
Source of truth for all agent names, trigger conditions, costs and thresholds is [`PIPELINE.md`](../PIPELINE.md).

---

## Diagram 1 — 5-Agent Pipeline Flow

The selective, cost-aware routing logic. Most addresses never touch the LLM.

```mermaid
flowchart TD
    IN([Raw Address String]):::input --> A1

    A1["**Agent 1 — Deterministic Parser**
    bharataddress.parse()
    pincode → city / district / state
    landmark cue detection · Devanagari check
    ⏱ ~0.2–0.5 ms · 💲 $0"]:::always

    A1 --> D1{Trigger A2?
    freetext conf < 0.6
    OR landmark cue + no landmark
    OR Devanagari detected}

    D1 -- YES --> A2["**Agent 2 — IndicBERT NER**
    shiprocket-ai/open-indicbert-…
    23-label BIO NER
    fills: landmark, locality,
    building_name, road, floor
    ⏱ 35–60 ms CPU · 💲 $0 (local model)"]:::selective

    D1 -- NO --> D2

    A2 --> D2{Trigger A3?
    landmark ≠ null
    AND center point available}

    D2 -- YES --> A3["**Agent 3 — OSM Landmark Resolution**
    Overpass API + bharataddress phonetic
    2 km radius → 5 km retry
    min match score: 0.55
    ⏱ 300–1200 ms · Redis cached: < 1 ms · 💲 $0"]:::selective

    D2 -- NO --> A4

    A3 --> A4

    A4["**Agent 4 — Confidence Arbitration**
    combined = 0.50×A1 + 0.15×A1_freetext
              + 0.10×A2_ner + 0.25×A3_score
    ⏱ < 1 ms · 💲 $0 (rules only)"]:::always

    A4 --> D3{Confidence tier?}

    D3 -- "≥ 0.80 HIGH" --> FINALIZE["Finalize
    needs_human_review = false
    💲 $0 LLM cost"]:::high

    D3 -- "0.50–0.79 MEDIUM" --> LLM["ONE LLM call
    Claude Haiku / configurable
    scoped disambiguation prompt
    ⏱ 400–1500 ms
    💲 ~$0.00015/call"]:::medium

    D3 -- "< 0.50 LOW" --> REVIEW["Flag needs_human_review = true
    Return best partial result
    No silent guessing
    💲 $0 LLM cost"]:::low

    LLM --> A5
    FINALIZE --> A5
    REVIEW --> A5

    A5["**Agent 5 — Self-Check & Output Formatting**
    coord within pincode radius?
    DIGIPIN generation (4m × 4m grid)
    Anchor type & accuracy radius derivation:
      • landmark → ~150m radius
      • pincode_centroid → ~2000m radius
      • unresolved → null
    bharataddress.validate()
    silent-guess enforcement
    ⏱ 1–3 ms · 💲 $0"]:::always

    A5 --> OUT([AddressResolution JSON]):::output

    classDef input    fill:#1e293b,stroke:#38bdf8,color:#e2e8f0,font-weight:bold
    classDef output   fill:#1e293b,stroke:#34d399,color:#e2e8f0,font-weight:bold
    classDef always   fill:#0f172a,stroke:#6366f1,color:#e2e8f0
    classDef selective fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    classDef high     fill:#052e16,stroke:#22c55e,color:#bbf7d0
    classDef medium   fill:#1c1917,stroke:#f59e0b,color:#fef3c7
    classDef low      fill:#1c0a09,stroke:#ef4444,color:#fecaca
```

**Reading guide:**
- **Purple border** = always-runs agents (A1, A4, A5)
- **Amber border** = selective agents triggered by condition (A2, A3)
- **Green → Amber → Red** = confidence tier routing
- 85–95% of traffic exits at HIGH (zero LLM cost)

---

## Diagram 2 — Full-Stack System View

Both frontends, the API layer, the 5-agent pipeline, external services, and the review-loop feedback path.

```mermaid
flowchart LR
    subgraph FRONTENDS["Frontend Layer"]
        direction TB
        PG["🖥 Resolution Playground
        Vite + React 19 + Tailwind
        localhost:5173
        — Benchmark carousel
        — Live agent trace
        — Leaflet OSM map
        — DIGIPIN card
        — Pin-drag confirmation"]
        RD["🖥 Ops Review Dashboard
        Vite + React 19 + Tailwind
        localhost:5174
        — Prometheus telemetry header
        — Paginated review queue
        — Review detail drawer
        — Draggable map pin"]
    end

    subgraph API["FastAPI Backend  (:8000)"]
        direction TB
        R1["POST /v1/resolve"]
        R2["POST /v1/resolve/batch"]
        R3["GET  /v1/resolve/{id}"]
        R4["GET  /v1/review/queue"]
        R5["POST /v1/review/{id}/confirm"]
        R6["POST /v1/review/{id}/resolve"]
        R7["GET  /v1/health/*"]
        R8["GET  /v1/metrics"]
    end

    subgraph PIPELINE["5-Agent Pipeline"]
        direction TB
        P1["A1 Parser"]
        P2["A2 NER"]
        P3["A3 OSM"]
        P4["A4 Arbitration"]
        P5["A5 Self-Check"]
        P1 --> P2 --> P3 --> P4 --> P5
    end

    subgraph STORAGE["Persistent State"]
        direction TB
        PG_DB[("PostgreSQL 15
        resolutions
        raw_address_staging
        corrections")]
        REDIS[("Redis 7
        Rate limiter
        Overpass cache
        Circuit breaker state")]
    end

    subgraph EXTERNAL["External Services"]
        direction TB
        OSM["OpenStreetMap
        Overpass API
        (free, rate-limited)"]
        LLM["LLM Provider
        Claude Haiku / configurable
        MEDIUM tier only
        ~5–15% of requests"]
    end

    subgraph FEEDBACK["Review Loop Feedback"]
        CORRECT["CorrectionModel
        original vs corrected
        lat/lng + fields"]
        EXPORT["backend/scripts/export_corrections.py
        → corrections.jsonl
        fine-tuning dataset"]
        WEBHOOK["HMAC-signed Webhook
        → e-commerce backend"]
    end

    PG -->|"POST /v1/resolve\nX-API-Key"| R1
    RD -->|"GET /v1/review/queue\nX-API-Key"| R4
    RD -->|"POST /v1/review/{id}/confirm"| R5
    RD -->|"POST /v1/review/{id}/resolve"| R6

    R1 --> PIPELINE
    R2 --> PIPELINE

    PIPELINE --> P3 -->|Overpass query| OSM
    PIPELINE --> P4 -->|MEDIUM tier only| LLM

    R1 --> PG_DB
    R3 --> PG_DB
    R4 --> PG_DB
    R5 --> PG_DB
    R6 --> CORRECT

    API <-->|"Rate limit\nCache\nCB state"| REDIS

    CORRECT --> EXPORT
    CORRECT --> WEBHOOK
    R6 --> WEBHOOK

    classDef fe   fill:#1e1b4b,stroke:#818cf8,color:#e0e7ff
    classDef api  fill:#0f172a,stroke:#38bdf8,color:#e0f2fe
    classDef pip  fill:#0a0f1a,stroke:#6366f1,color:#e2e8f0
    classDef db   fill:#0f2a1a,stroke:#34d399,color:#d1fae5
    classDef ext  fill:#2a1f0a,stroke:#f59e0b,color:#fef3c7
    classDef fb   fill:#1c0a0a,stroke:#f87171,color:#fee2e2

    class PG,RD fe
    class R1,R2,R3,R4,R5,R6,R7,R8 api
    class P1,P2,P3,P4,P5 pip
    class PG_DB,REDIS db
    class OSM,LLM ext
    class CORRECT,EXPORT,WEBHOOK fb
```

---

## Diagram 3 — Deployment Topology

Kubernetes pods, shared state, and data-residency note.

```mermaid
flowchart TD
    subgraph INTERNET["Public Internet"]
        CLIENT["Browser / Mobile\nE-commerce Checkout"]
    end

    subgraph INDIA["☁ India Region — ap-south-1 Mumbai\n(DPDP Act 2023 mandatory)"]

        LB["Load Balancer\nNGINX / AWS ALB"]

        subgraph K8S["Kubernetes Cluster"]
            subgraph PODS["Pata API Pods  (HPA: min 2 / max 10)"]
                POD1["pata-api pod 1\n2 vCPU / 4 GB RAM\nIndicBERT in memory"]
                POD2["pata-api pod 2\n2 vCPU / 4 GB RAM"]
                PODN["pata-api pod N\n↑ scales at CPU > 70%"]
            end

            PURGE["CronJob: pata-ttl-purge\nHourly raw address deletion\n(DPDP 24h TTL)"]
        end

        subgraph DATA["Data Layer"]
            PG["PostgreSQL 15\nPrimary + Replica\nresolutions · corrections\nraw_address_staging"]
            REDIS["Redis 7\nRate limiter\nOverpass cache\nCircuit breaker state"]
        end

        subgraph FRONTENDS["Static Frontend Hosting\n(Vercel / CDN)"]
            FE1["Resolution Playground\n:5173"]
            FE2["Ops Review Dashboard\n:5174"]
        end
    end

    subgraph EXTERNAL["External APIs (HTTPS)"]
        OSM["OpenStreetMap\nOverpass API"]
        LLM_EXT["LLM Provider\nClaude Haiku\n(MEDIUM tier, ~10% of reqs)"]
    end

    CLIENT -->|"HTTPS"| LB
    CLIENT -->|"Static assets"| FE1
    CLIENT -->|"Static assets"| FE2
    LB --> POD1
    LB --> POD2
    LB --> PODN

    POD1 <--> PG
    POD2 <--> PG
    PODN <--> PG
    POD1 <--> REDIS
    POD2 <--> REDIS
    PODN <--> REDIS

    PURGE --> PG

    POD1 -->|"Agent 3\nRedis-cached"| OSM
    POD1 -->|"Agent 4\nMEDIUM tier only"| LLM_EXT

    FE1 -->|"X-API-Key\nPOST /v1/resolve"| LB
    FE2 -->|"X-API-Key\nGET /v1/review/*"| LB

    classDef lb    fill:#0f172a,stroke:#38bdf8,color:#e0f2fe
    classDef pod   fill:#0a0f1a,stroke:#6366f1,color:#e2e8f0
    classDef data  fill:#0f2a1a,stroke:#34d399,color:#d1fae5
    classDef fe    fill:#1e1b4b,stroke:#818cf8,color:#e0e7ff
    classDef ext   fill:#2a1f0a,stroke:#f59e0b,color:#fef3c7
    classDef purge fill:#1c0a0a,stroke:#f87171,color:#fee2e2
    classDef box   fill:#0a0a0a,stroke:#374151,color:#9ca3af

    class LB lb
    class POD1,POD2,PODN pod
    class PG,REDIS data
    class FE1,FE2 fe
    class OSM,LLM_EXT ext
    class PURGE purge
```

**Deployment notes:**
- All three data stores (Postgres, Redis, raw_address_staging) must remain in the India region per DPDP Act 2023.
- IndicBERT NER model (~125 MB) is loaded into pod memory at startup via `preload_models()` — no external inference endpoint.
- The Overpass cache (Redis, TTL 24h) means most Agent 3 calls cost < 1ms after warm-up.
- HPA scales on CPU; sale event spike config is in `k8s/hpa.yaml` (4 pods/60s scale-up, 5-min scale-down stabilization).

---

*Last updated: Stage 6 (August 2026). Mermaid renders natively on GitHub.*
