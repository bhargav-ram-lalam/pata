"""
tests/test_review.py
====================
Integration tests for the Stage 4 human-review loop endpoints.

Tests: GET /v1/review/queue, POST /v1/review/{id}/confirm,
       POST /v1/review/{id}/resolve, review_status lifecycle,
       CorrectionModel persistence, webhook (mocked).
"""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from persistence.database import init_db, SessionLocal
from persistence.models import ResolutionModel, CorrectionModel

API_KEY = "test_api_key_stage3"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_resolution(
    review_status: str = "pending_review",
    confidence: float = 0.35,
    needs_human_review: bool = True,
    request_id: str = None,
) -> str:
    """Insert a test resolution directly into the DB. Returns request_id."""
    rid = request_id or str(uuid.uuid4())
    db = SessionLocal()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        rec = ResolutionModel(
            request_id=rid,
            parsed={"pincode": "560001", "city": "Bangalore"},
            confidence=confidence,
            needs_human_review=needs_human_review,
            review_status=review_status,
            evidence={"agent4_tier": "low"},
            pipeline_trace=[],
            created_at=now - datetime.timedelta(minutes=30),
            ttl_for_raw_retention=(now + datetime.timedelta(hours=24)).isoformat(),
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()
    return rid


# ---------------------------------------------------------------------------
# 1. Review queue tests
# ---------------------------------------------------------------------------

def test_review_queue_requires_auth(client):
    """Review queue must require valid API key."""
    resp = client.get("/v1/review/queue")
    assert resp.status_code == 401


def test_review_queue_returns_pending(client):
    """GET /v1/review/queue returns pending_review items sorted by confidence."""
    # Insert two pending resolutions with different confidence levels
    low_id = _insert_resolution(review_status="pending_review", confidence=0.30)
    mid_id = _insert_resolution(review_status="pending_review", confidence=0.45)
    # Insert one that is already confirmed (should NOT appear in queue)
    _insert_resolution(review_status="confirmed", confidence=0.20)

    resp = client.get("/v1/review/queue?sort_by=confidence&page=1&page_size=50",
                      headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] >= 2
    assert data["page"] == 1
    assert "items" in data

    pending_ids = [item["request_id"] for item in data["items"]]
    assert low_id in pending_ids
    assert mid_id in pending_ids

    # Lowest confidence should appear first
    confidences = [item["confidence"] for item in data["items"]]
    assert confidences == sorted(confidences)


def test_review_queue_pagination(client):
    """Pagination parameters are respected."""
    # Ensure at least 3 pending items exist
    for _ in range(3):
        _insert_resolution(review_status="pending_review")

    resp = client.get("/v1/review/queue?page=1&page_size=2",
                      headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["page_size"] == 2


def test_review_queue_invalid_params(client):
    """Invalid pagination/sort params return 422."""
    resp = client.get("/v1/review/queue?sort_by=invalid",
                      headers={"X-API-Key": API_KEY})
    assert resp.status_code == 422

    resp2 = client.get("/v1/review/queue?page=0",
                       headers={"X-API-Key": API_KEY})
    assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# 2. Confirm endpoint tests
# ---------------------------------------------------------------------------

def test_confirm_resolution_success(client):
    """POST /confirm sets review_status='confirmed'."""
    rid = _insert_resolution(review_status="pending_review", confidence=0.55)

    with patch("api.review.fire_correction_webhook"):
        resp = client.post(
            f"/v1/review/{rid}/confirm",
            json={"reviewer_id": "test_agent_007"},
            headers={"X-API-Key": API_KEY},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["request_id"] == rid

    # Verify DB state
    db = SessionLocal()
    try:
        rec = db.query(ResolutionModel).filter(ResolutionModel.request_id == rid).first()
        assert rec is not None
        assert rec.review_status == "confirmed"
    finally:
        db.close()


def test_confirm_resolution_not_found(client):
    """Confirming a non-existent request_id returns 404."""
    resp = client.post(
        "/v1/review/non-existent-id/confirm",
        json={"reviewer_id": "test_reviewer"},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Correction (resolve) endpoint tests
# ---------------------------------------------------------------------------

def test_submit_correction_success(client):
    """POST /resolve creates CorrectionModel and sets review_status='corrected'."""
    rid = _insert_resolution(review_status="pending_review", confidence=0.28)

    with patch("api.review.fire_correction_webhook", return_value=True):
        resp = client.post(
            f"/v1/review/{rid}/resolve",
            json={
                "reviewer_id": "reviewer_abc",
                "corrected_lat": 12.9801,
                "corrected_lng": 77.5900,
                "corrected_parsed": {"landmark": "Apollo Hospital"},
                "notes": "Customer confirmed correct location",
            },
            headers={"X-API-Key": API_KEY},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "corrected"
    assert data["request_id"] == rid

    # Verify resolution status updated
    db = SessionLocal()
    try:
        rec = db.query(ResolutionModel).filter(ResolutionModel.request_id == rid).first()
        assert rec.review_status == "corrected"

        # Verify CorrectionModel was created
        corr = db.query(CorrectionModel).filter(CorrectionModel.request_id == rid).first()
        assert corr is not None
        assert corr.reviewer_id == "reviewer_abc"
        assert corr.corrected_lat == pytest.approx(12.9801, rel=1e-4)
        assert corr.corrected_lng == pytest.approx(77.5900, rel=1e-4)
        assert corr.corrected_parsed == {"landmark": "Apollo Hospital"}
        assert corr.turnaround_seconds is not None
        assert corr.turnaround_seconds > 0
    finally:
        db.close()


def test_submit_correction_fires_webhook(client):
    """Correction endpoint fires webhook (mocked here)."""
    rid = _insert_resolution(review_status="pending_review")

    with patch("api.review.fire_correction_webhook", return_value=True) as mock_wh:
        client.post(
            f"/v1/review/{rid}/resolve",
            json={
                "reviewer_id": "reviewer_webhook_test",
                "corrected_lat": 12.9001,
                "corrected_lng": 77.5001,
            },
            headers={"X-API-Key": API_KEY},
        )
        mock_wh.assert_called_once()
        call_kwargs = mock_wh.call_args
        assert call_kwargs.kwargs.get("request_id") == rid or call_kwargs.args[0] == rid


def test_correction_invalid_lat(client):
    """Coordinates outside India bounds are rejected."""
    rid = _insert_resolution(review_status="pending_review")
    resp = client.post(
        f"/v1/review/{rid}/resolve",
        json={
            "reviewer_id": "reviewer_test",
            "corrected_lat": 51.5,  # London — outside India bounds
            "corrected_lng": 77.5,
        },
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 422


def test_correction_not_found(client):
    """Correcting a non-existent ID returns 404."""
    resp = client.post(
        "/v1/review/no-such-id/resolve",
        json={"reviewer_id": "reviewer_test"},
        headers={"X-API-Key": API_KEY},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Review status set by save_resolution
# ---------------------------------------------------------------------------

def test_save_resolution_sets_review_status():
    """save_resolution sets pending_review when needs_human_review=True."""
    from persistence.repository import save_resolution
    from pipeline import AddressResolution
    import time

    db = SessionLocal()
    rid = str(uuid.uuid4())
    try:
        res = AddressResolution(
            raw_address="garbled address xyz",
            parsed={"pincode": "560001"},
            digipin=None,
            latitude=12.97,
            longitude=77.59,
            confidence=0.30,
            needs_human_review=True,
            evidence={"agent4_tier": "low"},
            pipeline_trace=[],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ttl_for_raw_retention=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 86400)),
        )
        record = save_resolution(db, rid, res, "garbled address xyz")
        assert record.review_status == "pending_review"
    finally:
        db.close()


def test_save_resolution_auto_confirmed_for_high_confidence():
    """save_resolution sets auto_confirmed when needs_human_review=False."""
    from persistence.repository import save_resolution
    from pipeline import AddressResolution
    import time

    db = SessionLocal()
    rid = str(uuid.uuid4())
    try:
        res = AddressResolution(
            raw_address="Bengaluru 560001",
            parsed={"pincode": "560001"},
            digipin="M4P7R2Q8K1",
            latitude=12.97,
            longitude=77.59,
            confidence=0.87,
            needs_human_review=False,
            evidence={"agent4_tier": "high"},
            pipeline_trace=[],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ttl_for_raw_retention=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 86400)),
        )
        record = save_resolution(db, rid, res, "Bengaluru 560001")
        assert record.review_status == "auto_confirmed"
    finally:
        db.close()
