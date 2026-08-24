# Checkout Integration Example

Demonstrates Pata's e-commerce checkout integration — the original brief's
core premise: **resolve addresses at order-placement time, not as an overnight batch job**.

## Prerequisites

```bash
# Start the full stack (Postgres + Redis + Pata API)
docker-compose up -d

# Or for local dev:
uvicorn api.main:app --port 8000

# Install demo dependencies
pip install httpx
```

## Run the Demo

```bash
# Against local dev server
python examples/checkout_integration/simulate_checkout.py

# Against docker-compose stack
PATA_API_URL=http://localhost:8000 python examples/checkout_integration/simulate_checkout.py

# With a specific API key
PATA_API_KEY=pata_dev_key python examples/checkout_integration/simulate_checkout.py
```

## What It Shows

The demo runs three checkout scenarios and prints the full pipeline trace:

| Scenario | Confidence | Checkout Action |
|----------|-----------|-----------------|
| Clean pincode address | HIGH (≥0.80) | Auto-confirm → order created immediately |
| Ambiguous landmark | MEDIUM (0.50–0.79) | Show customer map-pin / route COD orders to review queue |
| Garbled / incomplete | LOW (<0.50) | Hold order → route to human review queue |

## Expected Output (abbreviated)

```
══════════════════════════════════════════════════════════════════════
  PATA E-COMMERCE CHECKOUT INTEGRATION DEMO
══════════════════════════════════════════════════════════════════════

SCENARIO 1: HIGH confidence — clean pincode address
──────────────────────────────────────────────────────
  RAW INPUT    : 'Flat 402, Shanti Heights, Bannerghatta Road, Bengaluru 560076'

  PIPELINE TRACE:
    ✓ Agent1_DeterministicParser          3.2ms
    ⊘ Agent2_LandmarkNER                  skipped
    ⊘ Agent3_LandmarkResolution           skipped
    ✓ Agent4_ConfidenceArbitration        0.8ms
    ✓ Agent5_SelfCheck                    1.1ms

  RESULT:
    Confidence  : 0.850  [HIGH tier]
    Latency     : 12.4ms
    DIGIPIN     : M4P7R2Q8K1

  CHECKOUT DECISION:
  ✓ HIGH CONFIDENCE — auto-confirming address, creating order
   → [ORDER CREATED] #ORD-A1B2C3D4
```

## Review Queue Integration

After LOW/MEDIUM confidence resolutions are routed to the queue:

```bash
# See pending reviews
curl -H "X-API-Key: pata_dev_key" http://localhost:8000/v1/review/queue

# Confirm a result was correct
curl -X POST -H "X-API-Key: pata_dev_key" \
  -H "Content-Type: application/json" \
  -d '{"reviewer_id": "agent_007"}' \
  http://localhost:8000/v1/review/{request_id}/confirm

# Submit a correction (triggers signed webhook to update order)
curl -X POST -H "X-API-Key: pata_dev_key" \
  -H "Content-Type: application/json" \
  -d '{"reviewer_id":"agent_007","corrected_lat":12.9801,"corrected_lng":77.5900}' \
  http://localhost:8000/v1/review/{request_id}/resolve
```
