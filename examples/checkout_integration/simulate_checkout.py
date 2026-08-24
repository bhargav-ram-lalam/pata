"""
examples/checkout_integration/simulate_checkout.py
===================================================
End-to-end e-commerce checkout integration demo for Pata.

Demonstrates the original brief's core premise: "run at order-placement time,
not as an overnight batch job."

This script simulates three checkout scenarios:
  1. HIGH confidence (≥0.80) — auto-confirm, proceed to order creation
  2. MEDIUM confidence (0.50–0.79) — show UX fallback (pin confirmation)
     or route to review queue for COD/high-value orders
  3. LOW confidence (<0.50) — route to review queue, hold order

Usage:
    # Requires Pata API running locally
    pip install httpx
    python examples/checkout_integration/simulate_checkout.py

    # With custom API endpoint
    PATA_API_URL=http://localhost:8000 python examples/checkout_integration/simulate_checkout.py
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_HTTPX = False

# Configuration
API_URL = os.getenv("PATA_API_URL", "http://localhost:8000")
API_KEY = os.getenv("PATA_API_KEY", "pata_dev_key")
HIGH_CONF = float(os.getenv("PATA_HIGH_CONF", "0.80"))
MEDIUM_CONF = float(os.getenv("PATA_MEDIUM_CONF", "0.50"))

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Test Addresses (representative Indian e-commerce scenarios)
# ---------------------------------------------------------------------------

TEST_ADDRESSES = [
    {
        "scenario": "HIGH confidence — clean pincode address",
        "address": "Flat 402, Shanti Heights, Bannerghatta Road, Bengaluru 560076",
        "hint_lat": 12.9003,
        "hint_lng": 77.5981,
        "order_value": 1200,
        "is_cod": False,
    },
    {
        "scenario": "MEDIUM confidence — ambiguous landmark, needs LLM",
        "address": "Near old post office, Koramangala, Bengaluru",
        "hint_lat": None,
        "hint_lng": None,
        "order_value": 3500,
        "is_cod": False,
    },
    {
        "scenario": "LOW confidence — garbled / incomplete address",
        "address": "opp police stn, near big bazar, some place 000000",
        "hint_lat": None,
        "hint_lng": None,
        "order_value": 8000,
        "is_cod": True,
    },
]


def call_pata_resolve(address: str, hint_lat: Optional[float], hint_lng: Optional[float]) -> tuple[dict, float]:
    """Call POST /v1/resolve and return (result_dict, latency_ms)."""
    payload = {"address": address}
    if hint_lat is not None:
        payload["hint_lat"] = hint_lat
    if hint_lng is not None:
        payload["hint_lng"] = hint_lng

    payload_json = json.dumps(payload).encode()
    t0 = time.perf_counter()

    if HAS_HTTPX:
        resp = httpx.post(f"{API_URL}/v1/resolve", json=payload, headers=HEADERS, timeout=10.0)
        latency_ms = (time.perf_counter() - t0) * 1000
        result = resp.json()
    else:
        import urllib.request
        req = urllib.request.Request(
            f"{API_URL}/v1/resolve",
            data=payload_json,
            headers=HEADERS,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            result = json.loads(resp.read().decode())

    return result, latency_ms


def route_to_review_queue(request_id: str, reason: str) -> None:
    """
    Simulate routing a resolution to the human-review queue.
    In production, the resolution is already in the queue (review_status='pending_review').
    This function prints the action an e-commerce system would take.
    """
    print(f"   → [REVIEW QUEUE] Routing {request_id} to human review: {reason}")
    print(f"     API call: GET {API_URL}/v1/review/queue")
    print(f"     After human correction → Pata fires signed webhook to update order delivery address")


def mock_map_pin_confirmation(result: dict) -> bool:
    """
    Mock UX: Show the customer a map with the resolved pin and ask them to confirm/adjust.
    Returns True if customer confirms (simulated), False if they adjust.

    In a real integration, this would open a map UI (e.g., Google Maps embedded).
    """
    print(f"   → [MAP UX] Showing customer map pin at ({result.get('latitude'):.4f}, {result.get('longitude'):.4f})")
    print(f"     [MOCK] Customer confirms pin is correct → proceeding")
    return True  # Simulated customer confirmation


def simulate_order_creation(address_result: dict, order_id: str, latency_ms: float) -> None:
    """Simulate successful order creation after HIGH/confirmed address."""
    digipin = address_result.get("digipin", "N/A")
    lat = address_result.get("latitude")
    lng = address_result.get("longitude")
    parsed = address_result.get("parsed", {})
    print(f"   → [ORDER CREATED] #{order_id}")
    print(f"     DIGIPIN: {digipin}")
    print(f"     Delivery coords: ({lat}, {lng})")
    print(f"     City: {parsed.get('city', 'unknown')}, Pincode: {parsed.get('pincode', 'unknown')}")
    print(f"     Address resolution latency: {latency_ms:.1f}ms ✓")


def run_checkout_flow():
    """Run the full checkout simulation with all three confidence tiers."""
    print("\n" + "═" * 70)
    print("  PATA E-COMMERCE CHECKOUT INTEGRATION DEMO")
    print(f"  API: {API_URL} | Date: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("═" * 70)

    for idx, scenario in enumerate(TEST_ADDRESSES, 1):
        print(f"\n{'─' * 70}")
        print(f"SCENARIO {idx}: {scenario['scenario']}")
        print(f"{'─' * 70}")
        print(f"  RAW INPUT    : {scenario['address']!r}")
        print(f"  Order value  : ₹{scenario['order_value']:,} | COD: {scenario['is_cod']}")

        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        try:
            result, latency_ms = call_pata_resolve(
                scenario["address"],
                scenario.get("hint_lat"),
                scenario.get("hint_lng"),
            )
        except Exception as exc:
            print(f"  ✗ Pata API call failed: {exc}")
            print(f"    (Is the service running? Start with: uvicorn api.main:app --port 8000)")
            continue

        confidence = result.get("confidence", 0.0)
        needs_review = result.get("needs_human_review", True)
        request_id = result.get("request_id", "unknown")
        evidence = result.get("evidence", {})
        trace = result.get("pipeline_trace", [])

        print(f"\n  PIPELINE TRACE:")
        agents_ran = [t["agent"] for t in trace if t.get("ran")]
        for t in trace:
            status = "✓" if t.get("ran") else "⊘"
            latency = f"{t.get('latency_ms', 0):.1f}ms" if t.get("ran") else "skipped"
            print(f"    {status} {t.get('agent', '?'):<40} {latency}")

        tier = evidence.get("agent4_tier", "unknown").upper()
        print(f"\n  RESULT:")
        print(f"    Confidence  : {confidence:.3f}  [{tier} tier]")
        print(f"    Needs review: {needs_review}")
        print(f"    Latency     : {latency_ms:.1f}ms")
        print(f"    Request ID  : {request_id}")
        print(f"    Coordinates : ({result.get('latitude')}, {result.get('longitude')})")
        print(f"    DIGIPIN     : {result.get('digipin')}")

        print(f"\n  CHECKOUT DECISION:")

        # ── HIGH confidence → auto-confirm ──────────────────────────────────
        if confidence >= HIGH_CONF:
            print(f"  ✓ HIGH CONFIDENCE — auto-confirming address, creating order")
            simulate_order_creation(result, order_id, latency_ms)

        # ── MEDIUM confidence → map pin UX or review queue ──────────────────
        elif confidence >= MEDIUM_CONF:
            print(f"  ⚠ MEDIUM CONFIDENCE — applying UX fallback")

            if scenario["is_cod"] or scenario["order_value"] >= 5000:
                # High-value / COD: don't risk wrong delivery → review queue
                print(f"  → High-value / COD order: routing to human review queue")
                route_to_review_queue(request_id, "medium_confidence + high_value_cod")
                print(f"  → Order {order_id} HELD pending review")
            else:
                # Standard order: show map pin to customer
                customer_confirmed = mock_map_pin_confirmation(result)
                if customer_confirmed:
                    print(f"  ✓ Customer confirmed pin — creating order")
                    simulate_order_creation(result, order_id, latency_ms)
                else:
                    print(f"  → Customer adjusted pin — routing to manual review")
                    route_to_review_queue(request_id, "customer_pin_adjusted")

        # ── LOW confidence → review queue, hold order ────────────────────────
        else:
            print(f"  ✗ LOW CONFIDENCE — address unresolvable, routing to human review")
            route_to_review_queue(request_id, "low_confidence")
            print(f"  → Order {order_id} HELD — customer will be contacted for address clarification")

    print(f"\n{'═' * 70}")
    print("  DEMO COMPLETE")
    print(f"  Review queue: GET {API_URL}/v1/review/queue")
    print(f"  Confirm:      POST {API_URL}/v1/review/{{request_id}}/confirm")
    print(f"  Correct:      POST {API_URL}/v1/review/{{request_id}}/resolve")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    run_checkout_flow()
