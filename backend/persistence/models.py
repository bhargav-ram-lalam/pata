"""
persistence/models.py
=====================
SQLAlchemy models for permanent non-PII resolution storage, short-lived raw
address staging (DPDP Act compliance), human-review loop, and corrections log.

Stage 4 additions:
  - ResolutionModel.review_status: tracks human review lifecycle
  - CorrectionModel: feedback dataset (original vs corrected values)
"""

from __future__ import annotations

import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    JSON,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from persistence.database import Base


class ResolutionModel(Base):
    """
    Long-lived non-PII resolution record.
    Preserves structured coordinates, confidence, and audit trail for delivery operations.
    NEVER stores raw_address.

    review_status lifecycle:
        pending_review  → set when needs_human_review=True (Stage 4)
        confirmed       → human confirms the result was correct
        corrected       → human submits a correction (see CorrectionModel)
        rejected        → human marks the result as unusable
        auto_confirmed  → set when needs_human_review=False (no review needed)
    """
    __tablename__ = "resolutions"

    request_id = Column(String(36), primary_key=True, index=True)
    parsed = Column(JSON, nullable=False)
    digipin = Column(String(15), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    confidence = Column(Float, nullable=False)
    needs_human_review = Column(Boolean, nullable=False, default=False)
    review_status = Column(
        String(20),
        nullable=False,
        default="auto_confirmed",
        index=True,
    )
    evidence = Column(JSON, nullable=False)
    pipeline_trace = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    ttl_for_raw_retention = Column(String(50), nullable=False)


class RawAddressStagingModel(Base):
    """
    Short-lived PII staging table with mandatory TTL enforcement.
    Deleted automatically by the background purge worker once purge_after <= now().
    """
    __tablename__ = "raw_address_staging"

    request_id = Column(
        String(36),
        ForeignKey("resolutions.request_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    raw_address = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    purge_after = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_raw_staging_purge_after", "purge_after"),
    )


class CorrectionModel(Base):
    """
    Human correction feedback dataset.

    Each row captures the original ML output vs the human-corrected version.
    This table is the training data source for future fine-tuning / gold-set
    expansion (see scripts/export_corrections.py).

    PRIVACY NOTE: corrected_parsed may contain human-entered address fields.
    Treat with the same DPDP Act guardrails as raw_address_staging.
    """
    __tablename__ = "corrections"

    id = Column(String(36), primary_key=True, index=True)
    request_id = Column(
        String(36),
        ForeignKey("resolutions.request_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id = Column(String(128), nullable=False)
    reviewed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    # Original ML output coordinates
    original_lat = Column(Float, nullable=True)
    original_lng = Column(Float, nullable=True)
    # Human-corrected coordinates (None if only parsed fields were corrected)
    corrected_lat = Column(Float, nullable=True)
    corrected_lng = Column(Float, nullable=True)
    # Structured field corrections
    original_parsed = Column(JSON, nullable=False)
    corrected_parsed = Column(JSON, nullable=True)
    # Optional freeform notes from the reviewer
    correction_notes = Column(Text, nullable=True)
    # Time from resolution creation to review completion (seconds)
    turnaround_seconds = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_corrections_request_id", "request_id"),
        Index("ix_corrections_reviewed_at", "reviewed_at"),
    )
