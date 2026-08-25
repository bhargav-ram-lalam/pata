"""
persistence/repository.py
========================
Data access repository functions for saving resolutions, querying results,
purging raw PII, and managing the human-review loop.

Stage 4 additions:
  - save_resolution now sets review_status based on needs_human_review
  - get_review_queue: paginated pending_review items
  - confirm_resolution / correct_resolution: review lifecycle transitions
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Optional, Any, List, Dict

from sqlalchemy.orm import Session
from persistence.database import SessionLocal
from persistence.models import ResolutionModel, RawAddressStagingModel, CorrectionModel

logger = logging.getLogger(__name__)


def save_resolution(
    db: Session,
    request_id: str,
    resolution: Any,  # AddressResolution instance or dict
    raw_address: str,
    ttl_hours: int = 24,
) -> ResolutionModel:
    """
    Atomically persist a resolution in the non-PII `resolutions` table
    and stage the raw address in `raw_address_staging` with an explicit TTL purge timestamp.

    Stage 4: sets review_status = "pending_review" when needs_human_review=True,
    otherwise "auto_confirmed".
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    purge_time = now_utc + datetime.timedelta(hours=ttl_hours)

    res_dict = resolution.model_dump() if hasattr(resolution, "model_dump") else (
        resolution.dict() if hasattr(resolution, "dict") else resolution
    )

    needs_review = res_dict.get("needs_human_review", False)
    review_status = "pending_review" if needs_review else "auto_confirmed"

    res_record = ResolutionModel(
        request_id=request_id,
        parsed=res_dict.get("parsed", {}),
        digipin=res_dict.get("digipin"),
        latitude=res_dict.get("latitude"),
        longitude=res_dict.get("longitude"),
        confidence=res_dict.get("confidence", 0.0),
        needs_human_review=needs_review,
        review_status=review_status,
        evidence=res_dict.get("evidence", {}),
        pipeline_trace=res_dict.get("pipeline_trace", []),
        created_at=now_utc,
        ttl_for_raw_retention=res_dict.get("ttl_for_raw_retention", purge_time.isoformat()),
    )

    staging_record = RawAddressStagingModel(
        request_id=request_id,
        raw_address=raw_address,
        created_at=now_utc,
        purge_after=purge_time,
    )

    try:
        db.add(res_record)
        db.flush()
        db.add(staging_record)
        db.commit()
        db.refresh(res_record)
        return res_record
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save resolution %s: %s", request_id, exc)
        raise


def get_resolution_by_id(db: Session, request_id: str) -> Optional[dict]:
    """
    Fetch a past non-PII resolution record by its request_id.
    """
    record = db.query(ResolutionModel).filter(ResolutionModel.request_id == request_id).first()
    if not record:
        return None

    ev = record.evidence or {}
    anchor = ev.get("anchor_type")
    if not anchor:
        coord_src = ev.get("coordinate_source", "")
        if "osm_poi" in coord_src or "landmark" in coord_src:
            anchor = "landmark"
        elif record.latitude is not None and record.longitude is not None:
            anchor = "pincode_centroid"
        else:
            anchor = "unresolved"

    acc_radius = ev.get("accuracy_radius_meters")
    if acc_radius is None:
        if anchor == "landmark":
            acc_radius = 150
        elif anchor == "pincode_centroid":
            acc_radius = 2000
        elif anchor == "osm_geocode":
            acc_radius = 500
        else:
            acc_radius = None

    return {
        "request_id": record.request_id,
        "parsed": record.parsed,
        "digipin": record.digipin,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "confidence": record.confidence,
        "anchor_type": anchor,
        "accuracy_radius_meters": acc_radius,
        "needs_human_review": record.needs_human_review,
        "review_status": record.review_status,
        "evidence": record.evidence,
        "pipeline_trace": record.pipeline_trace,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "ttl_for_raw_retention": record.ttl_for_raw_retention,
    }


def purge_expired_raw_addresses(db: Optional[Session] = None) -> int:
    """
    Delete expired rows from `raw_address_staging` where purge_after <= now_utc.
    Returns the count of purged rows.
    Works correctly on both SQLite (WAL) and Postgres.
    """
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        deleted_count = (
            db.query(RawAddressStagingModel)
            .filter(RawAddressStagingModel.purge_after <= now_utc)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted_count > 0:
            logger.info("AUDIT: Purged %d expired raw address staging records.", deleted_count)
        return deleted_count
    except Exception as exc:
        db.rollback()
        logger.error("Error during raw address staging purge: %s", exc)
        raise
    finally:
        if owns_session:
            db.close()


# ---------------------------------------------------------------------------
# Human-Review Loop — Stage 4
# ---------------------------------------------------------------------------

def get_review_queue(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "confidence",  # "confidence" | "timestamp"
) -> Dict[str, Any]:
    """
    Return paginated list of resolutions with review_status='pending_review'.
    Sorted by confidence ascending (lowest first) or created_at ascending.
    """
    query = db.query(ResolutionModel).filter(
        ResolutionModel.review_status == "pending_review"
    )

    if sort_by == "confidence":
        query = query.order_by(ResolutionModel.confidence.asc())
    else:
        query = query.order_by(ResolutionModel.created_at.asc())

    total = query.count()
    offset = (page - 1) * page_size
    records = query.offset(offset).limit(page_size).all()

    items = []
    for r in records:
        ev = r.evidence or {}
        anchor = ev.get("anchor_type")
        if not anchor:
            coord_src = ev.get("coordinate_source", "")
            if "osm_poi" in coord_src or "landmark" in coord_src:
                anchor = "landmark"
            elif r.latitude is not None and r.longitude is not None:
                anchor = "pincode_centroid"
            else:
                anchor = "unresolved"

        acc_radius = ev.get("accuracy_radius_meters")
        if acc_radius is None:
            if anchor == "landmark":
                acc_radius = 150
            elif anchor == "pincode_centroid":
                acc_radius = 2000
            elif anchor == "osm_geocode":
                acc_radius = 500
            else:
                acc_radius = None

        items.append({
            "request_id": r.request_id,
            "confidence": r.confidence,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "parsed": r.parsed,
            "digipin": r.digipin,
            "anchor_type": anchor,
            "accuracy_radius_meters": acc_radius,
            "evidence": r.evidence,
            "review_status": r.review_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
    }


def confirm_resolution(db: Session, request_id: str, reviewer_id: str = "api") -> Optional[dict]:
    """
    Mark a pending_review resolution as confirmed (human verified the ML result was correct).
    Returns the updated record dict, or None if not found / not in pending state.
    """
    record = db.query(ResolutionModel).filter(
        ResolutionModel.request_id == request_id
    ).first()

    if not record:
        return None

    if record.review_status not in ("pending_review",):
        logger.warning(
            "confirm_resolution called on %s which is in state '%s'",
            request_id, record.review_status,
        )

    record.review_status = "confirmed"
    try:
        db.commit()
        db.refresh(record)
        logger.info("Resolution %s confirmed by %s", request_id, reviewer_id)
        return get_resolution_by_id(db, request_id)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to confirm resolution %s: %s", request_id, exc)
        raise


def correct_resolution(
    db: Session,
    request_id: str,
    reviewer_id: str,
    corrected_lat: Optional[float] = None,
    corrected_lng: Optional[float] = None,
    corrected_parsed: Optional[dict] = None,
    correction_notes: Optional[str] = None,
) -> Optional[dict]:
    """
    Submit a human correction for a pending_review resolution.

    Creates a CorrectionModel record (the feedback dataset row) and updates
    review_status to 'corrected'.

    Returns the updated resolution dict, or None if not found.
    """
    record = db.query(ResolutionModel).filter(
        ResolutionModel.request_id == request_id
    ).first()

    if not record:
        return None

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    turnaround = None
    if record.created_at:
        delta = now_utc - record.created_at.replace(tzinfo=datetime.timezone.utc)
        turnaround = delta.total_seconds()

    correction = CorrectionModel(
        id=str(uuid.uuid4()),
        request_id=request_id,
        reviewer_id=reviewer_id,
        reviewed_at=now_utc,
        original_lat=record.latitude,
        original_lng=record.longitude,
        corrected_lat=corrected_lat,
        corrected_lng=corrected_lng,
        original_parsed=record.parsed or {},
        corrected_parsed=corrected_parsed,
        correction_notes=correction_notes,
        turnaround_seconds=turnaround,
    )

    record.review_status = "corrected"

    try:
        db.add(correction)
        db.commit()
        db.refresh(record)
        logger.info("Resolution %s corrected by %s (turnaround=%.1fs)", request_id, reviewer_id, turnaround or 0)
        return get_resolution_by_id(db, request_id)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save correction for %s: %s", request_id, exc)
        raise


def get_corrections_for_export(db: Session, limit: int = 10000) -> List[dict]:
    """
    Fetch all corrections for export (used by scripts/export_corrections.py).
    """
    records = db.query(CorrectionModel).order_by(CorrectionModel.reviewed_at.asc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "request_id": r.request_id,
            "reviewer_id": r.reviewer_id,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "original_lat": r.original_lat,
            "original_lng": r.original_lng,
            "corrected_lat": r.corrected_lat,
            "corrected_lng": r.corrected_lng,
            "original_parsed": r.original_parsed,
            "corrected_parsed": r.corrected_parsed,
            "correction_notes": r.correction_notes,
            "turnaround_seconds": r.turnaround_seconds,
        }
        for r in records
    ]
