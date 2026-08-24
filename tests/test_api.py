"""
tests/test_api.py
=================
Integration tests for the Pata FastAPI service endpoints.
"""

from __future__ import annotations

import os
import time
import pytest
from fastapi.testclient import TestClient

from api.main import app
from persistence.database import init_db, SessionLocal
from persistence.models import ResolutionModel, RawAddressStagingModel

API_KEY = "test_api_key_stage3"


@pytest.fixture(scope="module")
def client():
    """Client fixture that invokes FastAPI lifespan (database init, model warmup)."""
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Health & Probe Tests (Unauthenticated)
# ---------------------------------------------------------------------------

def test_health_live(client):
    """Liveness probe should return 200 without authentication."""
    resp = client.get("/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "live"}


def test_health_ready(client):
    """Readiness probe should return 200 when service is warmed up.

    Polls with retries to handle model loading time — IndicBERT warmup can take
    30–90s on a cold cache. This mirrors how container orchestrators use the probe.
    """
    import time
    deadline = time.time() + 120  # 2-minute max wait (covers cold model download)
    while time.time() < deadline:
        resp = client.get("/v1/health/ready")
        if resp.status_code == 200:
            assert resp.json() == {"status": "ready"}
            return
        time.sleep(2)
    # Final check: fail with a clear message if still not ready
    resp = client.get("/v1/health/ready")
    assert resp.status_code == 200, (
        f"Service not ready after 120s — preload_models() may have failed. "
        f"Last response: {resp.status_code} {resp.text}"
    )


def test_health_detailed_authenticated(client):
    """Detailed health check requires API key."""
    # Without auth -> 401
    resp_unauth = client.get("/v1/health")
    assert resp_unauth.status_code == 401

    # With auth -> 200
    resp = client.get("/v1/health", headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "components" in data
    assert "bharataddress_parser" in data["components"]


def test_metrics_endpoint(client):
    """Metrics endpoint should return Prometheus exposition format."""
    resp = client.get("/v1/metrics")
    assert resp.status_code == 200
    assert "pata_requests_total" in resp.text


# ---------------------------------------------------------------------------
# Authentication & Rate Limiting Tests
# ---------------------------------------------------------------------------

def test_auth_missing_key(client):
    resp = client.post("/v1/resolve", json={"address": "560001 Bangalore"})
    assert resp.status_code == 401
    assert "Missing API key" in resp.json()["detail"]


def test_auth_invalid_key(client):
    resp = client.post(
        "/v1/resolve",
        json={"address": "560001 Bangalore"},
        headers={"X-API-Key": "invalid_bogus_key"},
    )
    assert resp.status_code == 401
    assert "Invalid API key" in resp.json()["detail"]


def test_rate_limiting(client):
    """Exhausting rate limit bucket should return 429 Too Many Requests."""
    from api.auth import VALID_API_KEYS, rate_limiter, TokenBucket
    test_key = "rate_limit_test_key"
    VALID_API_KEYS.add(test_key)

    bucket = rate_limiter.buckets.setdefault(test_key, TokenBucket(rate=1.0, burst=1.0))
    bucket.tokens = 0.0
    bucket.last_update = time.time() + 100.0  # Prevent immediate replenishment

    resp = client.post(
        "/v1/resolve",
        json={"address": "560001 Bangalore"},
        headers={"X-API-Key": test_key},
    )
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]
    assert "Retry-After" in resp.headers


# ---------------------------------------------------------------------------
# Request Validation Tests
# ---------------------------------------------------------------------------

def test_validation_empty_address(client):
    resp = client.post(
        "/v1/resolve",
        json={"address": "   "},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 422


def test_validation_too_long_address(client):
    long_addr = "A" * 501
    resp = client.post(
        "/v1/resolve",
        json={"address": long_addr},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 422


def test_validation_invalid_hint_lat_lng(client):
    # Latitude out of India bounds (e.g. 50.0)
    resp = client.post(
        "/v1/resolve",
        json={"address": "Bangalore", "hint_lat": 50.0, "hint_lng": 77.0},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 422

    # Longitude out of India bounds (e.g. 120.0)
    resp2 = client.post(
        "/v1/resolve",
        json={"address": "Bangalore", "hint_lat": 12.0, "hint_lng": 120.0},
        headers={"X-API-Key": API_KEY},
    )
    assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# Single Resolve Happy Path & Persistence
# ---------------------------------------------------------------------------

def test_resolve_single_success(client):
    payload = {
        "address": "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru 560076",
        "hint_lat": 12.9003,
        "hint_lng": 77.5981,
    }
    resp = client.post("/v1/resolve", json=payload, headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.json()

    assert "X-Request-ID" in resp.headers
    req_id = resp.headers["X-Request-ID"]

    assert data["parsed"]["pincode"] == "560076"
    assert data["parsed"]["city"] == "Bangalore"
    assert data["digipin"] is not None
    assert data["confidence"] >= 0.50
    assert "ttl_for_raw_retention" in data

    # Verify DB persistence
    db = SessionLocal()
    try:
        # Check non-PII resolutions table
        res_record = db.query(ResolutionModel).filter(ResolutionModel.request_id == req_id).first()
        assert res_record is not None
        assert res_record.parsed["pincode"] == "560076"

        # Check raw_address_staging table
        staging_record = db.query(RawAddressStagingModel).filter(RawAddressStagingModel.request_id == req_id).first()
        assert staging_record is not None
        assert staging_record.raw_address == payload["address"]
    finally:
        db.close()

    # Test GET /v1/resolve/{request_id}
    fetch_resp = client.get(f"/v1/resolve/{req_id}", headers={"X-API-Key": API_KEY})
    assert fetch_resp.status_code == 200
    fetch_data = fetch_resp.json()
    assert fetch_data["request_id"] == req_id
    assert fetch_data["parsed"]["pincode"] == "560076"
    # Ensure raw_address is NOT in fetched non-PII record
    assert "raw_address" not in fetch_data


def test_get_resolution_not_found(client):
    resp = client.get("/v1/resolve/non-existent-uuid", headers={"X-API-Key": API_KEY})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Batch Resolve Tests
# ---------------------------------------------------------------------------

def test_resolve_batch(client):
    batch_payload = {
        "addresses": [
            {"address": "560001 Bangalore Karnataka"},
            {"address": "110001 New Delhi Connaught Place"},
            {"address": "400001 Mumbai Maharashtra"},
        ]
    }
    resp = client.post("/v1/resolve/batch", json=batch_payload, headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 3
    assert data["successful"] == 3
    assert data["failed"] == 0
    assert len(data["results"]) == 3
    assert data["results"][0]["success"] is True
    assert data["results"][0]["result"]["parsed"]["pincode"] == "560001"
