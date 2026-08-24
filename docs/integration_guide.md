# Pata Integration Guide for E-Commerce Partners

**Version:** `0.4.0` (Stage 4)  
**Last Updated:** August 2026  
**Audience:** Backend engineers integrating Pata address resolution at checkout

---

## Overview

Pata resolves unstructured Indian addresses into standardised, geocoded outputs **synchronously at order placement** — not as an overnight batch job. This guide explains how to integrate the `/v1/resolve` endpoint into your checkout flow, interpret confidence tiers, and consume the correction webhook.

---

## 1. Call `/v1/resolve` at Checkout

### Request

```http
POST /v1/resolve
X-API-Key: your_api_key
Content-Type: application/json

{
  "address": "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru 560076",
  "hint_lat": 12.9003,   // optional: device GPS latitude
  "hint_lng": 77.5981    // optional: device GPS longitude
}
```

**GPS hints** are optional but improve accuracy by 8–15% for ambiguous addresses (e.g. "near the church"). Pass the device location if available.

### Response

```json
{
  "raw_address": "Flat 402, Shanti Heights, ...",
  "parsed": {
    "pincode": "560076",
    "city": "Bangalore",
    "district": "Bangalore Urban",
    "state": "Karnataka",
    "landmark": "Apollo Hospital",
    "locality": "Bannerghatta Road",
    "building_name": "Shanti Heights"
  },
  "digipin": "M4P7R2Q8K1",
  "latitude": 12.9003,
  "longitude": 77.5981,
  "confidence": 0.87,
  "needs_human_review": false,
  "evidence": { "agent4_tier": "high", ... },
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "ttl_for_raw_retention": "2026-08-25T14:30:00Z"
}
```

---

## 2. Interpret Confidence Tiers

| `confidence` Range | Tier | `needs_human_review` | Recommended Checkout Action |
|---|---|---|---|
| ≥ 0.80 | **HIGH** | `false` | ✅ Auto-confirm. Proceed to order creation immediately. |
| 0.50 – 0.79 | **MEDIUM** | `false` | ⚠️ Show customer a map pin to confirm/adjust. For COD or high-value orders (>₹5,000), route to review queue instead. |
| < 0.50 | **LOW** | `true` | ❌ Do NOT guess. Hold order. Route to review queue. Contact customer. |

### Decision pseudocode

```python
result = pata.resolve(address)
confidence = result["confidence"]

if confidence >= 0.80:
    # HIGH — instant order creation
    create_order(result["digipin"], result["latitude"], result["longitude"])

elif confidence >= 0.50:
    if order.is_cod or order.value >= 5000:
        # High-stakes: wait for human confirmation
        hold_order()
        add_to_review_queue(result["request_id"])
    else:
        # Show map pin for customer self-correction
        show_map_pin_ui(result["latitude"], result["longitude"])
        if customer_confirms():
            create_order(...)
        else:
            hold_order()

else:
    # LOW — always hold and review
    hold_order()
    add_to_review_queue(result["request_id"])
    notify_customer("We need to verify your address.")
```

---

## 3. Expected Latency Budget

The following numbers are from the Stage 3 production load test (30 concurrent requests):

| Metric | Value | Notes |
|--------|-------|-------|
| **P50 latency** | ~45ms | Typical HIGH confidence (deterministic only) |
| **P95 latency** | ~320ms | When Agent 2 (IndicBERT NER) triggers |
| **P99 latency** | ~1,400ms | When Agent 3 (Overpass OSM) triggers (or LLM) |
| **Cache hit** | <1ms | Overpass results cached 24h in Redis |
| **Timeout (global)** | 5,000ms | Graceful degradation fallback |

**Recommendation:** Set your checkout timeout to **6 seconds** (5s pipeline + 1s overhead). Pata's internal timeout fires at 5s and returns a degraded result with `needs_human_review=true` rather than timing out your whole checkout page.

Stage 4 load test at 100 concurrent / 500 requests (Postgres + Redis):

| Metric | Value | Change from Stage 3 |
|--------|-------|---------------------|
| P50 | 48ms | +3ms (Redis round-trip) |
| P95 | 340ms | +20ms |
| P99 | 1,450ms | +50ms |
| Throughput | 312 req/s | +180% vs Stage 3 single-instance |

---

## 4. Human-Review Queue API

When `needs_human_review=true`, the resolution is automatically queued at `review_status=pending_review`. Your ops team can process it via:

### List the queue

```http
GET /v1/review/queue?sort_by=confidence&page=1&page_size=20
X-API-Key: your_api_key
```

**Response:** Sorted by lowest confidence first (most urgent cases at top).

### Confirm a result was correct

```http
POST /v1/review/{request_id}/confirm
X-API-Key: your_api_key
Content-Type: application/json

{"reviewer_id": "agent_007"}
```

Sets `review_status=confirmed`. Fire webhook if configured.

### Submit a correction

```http
POST /v1/review/{request_id}/resolve
X-API-Key: your_api_key
Content-Type: application/json

{
  "reviewer_id": "agent_007",
  "corrected_lat": 12.9801,
  "corrected_lng": 77.5900,
  "corrected_parsed": {
    "landmark": "Apollo Hospital",
    "locality": "Bannerghatta Road"
  },
  "notes": "Customer confirmed hospital entrance on left side of road"
}
```

Sets `review_status=corrected` **and** fires a signed webhook to your backend.

---

## 5. Consuming the Correction Webhook

When a human submits a correction, Pata POSTs a signed payload to `PATA_WEBHOOK_URL`:

### Payload

```json
{
  "event": "correction.submitted",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "reviewer_id": "agent_007",
  "timestamp": 1724516906,
  "original": {
    "latitude": 12.9003,
    "longitude": 77.5981
  },
  "corrected": {
    "latitude": 12.9801,
    "longitude": 77.5900,
    "parsed": {"landmark": "Apollo Hospital", "locality": "Bannerghatta Road"}
  }
}
```

### Signature Verification (Python)

```python
import hashlib
import hmac
import time

def verify_pata_webhook(body: bytes, timestamp_header: str, signature_header: str, secret: str) -> bool:
    """Verify Pata webhook authenticity."""
    timestamp = int(timestamp_header)
    
    # Reject events older than 5 minutes (replay protection)
    if abs(time.time() - timestamp) > 300:
        return False
    
    signed_str = f"{timestamp}.{body.decode('utf-8')}"
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        signed_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(
        signature_header,         # X-Pata-Signature header value (e.g. "sha256=abc...")
        f"sha256={expected_sig}"
    )
```

### Use the correction

```python
@app.post("/pata/webhook")
def pata_webhook(request: Request, body: bytes = Body(...)):
    timestamp = request.headers["X-Pata-Timestamp"]
    signature = request.headers["X-Pata-Signature"]
    
    if not verify_pata_webhook(body, timestamp, signature, PATA_WEBHOOK_SECRET):
        raise HTTPException(status_code=401)
    
    event = json.loads(body)
    if event["event"] == "correction.submitted":
        order = Order.get_by_pata_request_id(event["request_id"])
        order.update_delivery_coords(
            lat=event["corrected"]["latitude"],
            lng=event["corrected"]["longitude"],
        )
        order.release_hold()  # Allow fulfilment to proceed
```

---

## 6. Recommended API Deployment Topology

```
E-Commerce Checkout Server
        │
        │ POST /v1/resolve (sync, ≤5s timeout)
        ▼
   Load Balancer (India region — ap-south-1 Mumbai)
        │
   ┌────┴──────────────────────────────────────┐
   │  Pata API × N replicas (HPA: 2-10 pods)  │
   │                                           │
   │  Shared state:                            │
   │    Redis → rate limiter, Overpass cache,  │
   │            circuit breaker state          │
   │    PostgreSQL → resolutions, corrections  │
   └───────────────────────────────────────────┘
        │
        │ Webhook POST (async)
        ▼
   E-Commerce Backend (order address update)
```

> **DPDP Act 2023 Requirement:** All infrastructure **must** reside within India. Use AWS `ap-south-1` (Mumbai), GCP `asia-south1`, or Azure Central India. See [DEPLOYMENT.md](../DEPLOYMENT.md) for full compliance details.

---

## 7. Cost Reference

Based on measured LLM trigger rates (~10% of requests):

| Monthly Order Volume | LLM Calls | Estimated Cost |
|---|---|---|
| 10,000 orders | ~1,000 | ~$0.05 |
| 100,000 orders | ~10,000 | ~$0.47 |
| 1,000,000 orders | ~100,000 | ~$4.70 |

Agents 1, 2, 3 and 5 have **zero API cost** (local models + free OSM). Cost is only for Agent 4 LLM disambiguation calls on MEDIUM confidence addresses.

---

## 8. Quick Reference

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /v1/resolve` | ✓ | Resolve single address at checkout |
| `POST /v1/resolve/batch` | ✓ | Batch resolve up to 100 addresses |
| `GET /v1/review/queue` | ✓ | Human review backlog |
| `POST /v1/review/{id}/confirm` | ✓ | Mark result as confirmed-correct |
| `POST /v1/review/{id}/resolve` | ✓ | Submit correction → fires webhook |
| `GET /v1/health/live` | ✗ | Liveness probe |
| `GET /v1/health/ready` | ✗ | Readiness probe |
| `GET /v1/metrics` | ✗ | Prometheus metrics |
