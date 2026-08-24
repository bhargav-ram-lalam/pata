"""
api/review.py
=============
Human-review loop endpoints (Stage 4).

Closes the feedback path that Stage 3 left open:
  Stage 3 flags low-confidence results → Stage 4 provides the review queue
  and correction submission endpoints that let humans close the loop.

Endpoints:
  GET  /v1/review/queue                        — paginated pending_review list
  POST /v1/review/{request_id}/confirm         — mark result as confirmed-correct
  POST /v1/review/{request_id}/resolve         — submit a correction

All endpoints require a valid X-API-Key.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_api_key
from api.schemas import (
    ReviewQueueResponse,
    ConfirmRequest,
    CorrectRequest,
)
from persistence.database import get_db_session
from persistence.repository import (
    get_review_queue,
    confirm_resolution,
    correct_resolution,
    get_resolution_by_id,
)
from observability.metrics import (
    REVIEW_QUEUE_SIZE,
    REVIEWS_COMPLETED_TOTAL,
    REVIEW_TURNAROUND_SECONDS,
)
from examples.webhook_notification import fire_correction_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/review", tags=["human-review"])


@router.get(
    "/queue",
    response_model=ReviewQueueResponse,
    summary="Paginated list of resolutions pending human review",
    dependencies=[Depends(get_api_key)],
)
async def review_queue(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "confidence",
    db: Session = Depends(get_db_session),
):
    """
    Returns resolutions with review_status='pending_review', sorted by
    confidence ascending (lowest-confidence first) or by timestamp.

    Query parameters:
      - page: 1-indexed page number
      - page_size: items per page (max 100)
      - sort_by: 'confidence' (default) | 'timestamp'
    """
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="page_size must be 1–100")
    if sort_by not in ("confidence", "timestamp"):
        raise HTTPException(status_code=422, detail="sort_by must be 'confidence' or 'timestamp'")

    result = get_review_queue(db, page=page, page_size=page_size, sort_by=sort_by)

    # Update Prometheus gauge with current queue depth
    try:
        REVIEW_QUEUE_SIZE.set(result["total"])
    except Exception:
        pass

    return result


@router.post(
    "/{request_id}/confirm",
    summary="Confirm that a pending resolution was correct",
    dependencies=[Depends(get_api_key)],
)
async def confirm_review(
    request_id: str,
    body: ConfirmRequest,
    db: Session = Depends(get_db_session),
):
    """
    Mark a pending_review resolution as confirmed-correct.
    Sets review_status='confirmed' and emits review metrics.
    """
    record = get_resolution_by_id(db, request_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resolution '{request_id}' not found.",
        )

    t0 = time.time()
    updated = confirm_resolution(db, request_id, reviewer_id=body.reviewer_id or "api")
    elapsed = time.time() - t0

    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to confirm resolution.")

    # Prometheus metrics
    try:
        REVIEWS_COMPLETED_TOTAL.labels(outcome="confirmed").inc()
        if record.get("created_at"):
            import datetime
            created = datetime.datetime.fromisoformat(record["created_at"])
            now = datetime.datetime.now(datetime.timezone.utc)
            turnaround = (now - created.replace(tzinfo=datetime.timezone.utc)).total_seconds()
            REVIEW_TURNAROUND_SECONDS.observe(turnaround)
    except Exception as exc:
        logger.warning("Failed to record review metrics: %s", exc)

    logger.info("Resolution %s confirmed by %s", request_id, body.reviewer_id)
    return {"status": "confirmed", "request_id": request_id, "updated": updated}


@router.post(
    "/{request_id}/resolve",
    summary="Submit a human correction for a pending resolution",
    dependencies=[Depends(get_api_key)],
)
async def submit_correction(
    request_id: str,
    body: CorrectRequest,
    db: Session = Depends(get_db_session),
):
    """
    Submit a human correction.

    - Creates a CorrectionModel row (the fine-tuning feedback dataset entry).
    - Sets review_status='corrected'.
    - Fires a signed HMAC webhook (if PATA_WEBHOOK_URL is configured) so an
      e-commerce backend can update the order's delivery address automatically.
    """
    record = get_resolution_by_id(db, request_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resolution '{request_id}' not found.",
        )

    updated = correct_resolution(
        db,
        request_id=request_id,
        reviewer_id=body.reviewer_id,
        corrected_lat=body.corrected_lat,
        corrected_lng=body.corrected_lng,
        corrected_parsed=body.corrected_parsed,
        correction_notes=body.notes,
    )

    if updated is None:
        raise HTTPException(status_code=500, detail="Failed to save correction.")

    # Prometheus metrics
    try:
        REVIEWS_COMPLETED_TOTAL.labels(outcome="corrected").inc()
        if record.get("created_at"):
            import datetime
            created = datetime.datetime.fromisoformat(record["created_at"])
            now = datetime.datetime.now(datetime.timezone.utc)
            turnaround = (now - created.replace(tzinfo=datetime.timezone.utc)).total_seconds()
            REVIEW_TURNAROUND_SECONDS.observe(turnaround)
    except Exception as exc:
        logger.warning("Failed to record correction metrics: %s", exc)

    # Fire webhook (non-blocking; errors are logged but don't fail the request)
    try:
        fire_correction_webhook(
            request_id=request_id,
            original_lat=record.get("latitude"),
            original_lng=record.get("longitude"),
            corrected_lat=body.corrected_lat,
            corrected_lng=body.corrected_lng,
            corrected_parsed=body.corrected_parsed,
            reviewer_id=body.reviewer_id,
        )
    except Exception as exc:
        logger.warning("Webhook delivery failed for %s: %s", request_id, exc)

    logger.info("Correction submitted for %s by %s", request_id, body.reviewer_id)
    return {"status": "corrected", "request_id": request_id, "updated": updated}
