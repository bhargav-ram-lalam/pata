# Pata (पता) 📍

[![CI](https://github.com/bhargav-ram-lalam/pata/actions/workflows/ci.yml/badge.svg)](https://github.com/bhargav-ram-lalam/pata/actions/workflows/ci.yml)

> **Status: Stage 4 — Scale-Out, Human-Review Loop & E-Commerce Integration**

Pata is an AI-powered address resolution and standardization engine engineered specifically for the complexities of Indian last-mile logistics. Indian addresses are notorious for being unstructured, landmark-centric (e.g., *"behind Hanuman Mandir, opposite yellow water tank"*), colloquial, and frequently plagued by mismatched pincodes, missing house numbers, and mixed-script transliterations. Standard Western geocoders fail on these patterns. Pata combines deterministic postal parsing, fine-grained Named Entity Recognition (NER), spatial landmark validation, and confidence arbitration to resolve messy input into verified, deliverable coordinates and DIGIPIN codes.

**Stage 4** adds horizontal scalability (Redis-backed rate limiter, cache, circuit breaker; Postgres via Alembic), closes the human-review feedback loop, proves the e-commerce checkout integration end-to-end, and adds CI/CD + Kubernetes autoscaling manifests.

---

## Quick Start (Stage 4)

```bash
# Full stack: Postgres + Redis + Pata API
docker-compose up -d --build
alembic upgrade head

# Or local SQLite dev (no Redis/Postgres required)
uvicorn api.main:app --port 8000

# Run e-commerce checkout demo
python examples/checkout_integration/simulate_checkout.py

# Run all tests
pytest tests/ -v
```

### Key Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/resolve` | Resolve single address at checkout |
| `GET /v1/review/queue` | Human review backlog (pending_review) |
| `POST /v1/review/{id}/confirm` | Confirm ML result was correct |
| `POST /v1/review/{id}/resolve` | Submit correction → fires signed webhook |
| `GET /v1/metrics` | Prometheus metrics (incl. review loop) |

See [docs/integration_guide.md](docs/integration_guide.md) for e-commerce partner integration details.

---


## Setup & Reproduction

### Prerequisites
- Python ≥ 3.10 (tested on Python 3.13)
- Internet access for initial model weights download (~400MB) and pincode directory validation.

### 1. Create and Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On Linux / macOS (Bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

Install the core package in editable mode along with optional extras (`indic` transliteration and `fuzzy` matching):
```bash
pip install -e ".[indic,fuzzy,dev]"
```

Or directly via `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## Cache Directories Note

The underlying libraries store persistent datasets outside the repository workspace in user home directories:
- **`bharataddress` Cache**: `~/.cache/bharataddress/` stores the India Post pincode directory (~154,000+ records) and offline centroids.
- **Hugging Face Cache**: `~/.cache/huggingface/hub/` stores the IndicBERT model weights, tokenizer vocabularies, and config files for `shiprocket-ai/open-indicbert-indian-address-ner`.

These external directories are managed automatically by their respective libraries and should not be checked into Git.

---

## Running Foundation Validation

### Validate `bharataddress`
Executes test cases across all modules (`parse`, `pincode.lookup`, `digipin`, `format`, `validate`, `is_deliverable`, `phonetic`, `geocode`, `address_similarity`, `parse_batch`, and 50-run latency benchmark):
```bash
python scripts/validate_bharataddress.py
```

### Validate IndicBERT NER
Loads the model, inspects `id2label` token schema, runs inference on benchmark addresses, evaluates landmark capture on informal cue patterns, and logs cold-load + inference latency:
```bash
python scripts/validate_indicbert.py
```

---

## Stage 1 Deliverables & Documentation

- Comprehensive findings, latency benchmarks, and side-by-side field extraction comparison matrix: [docs/foundation_validation.md](docs/foundation_validation.md)
