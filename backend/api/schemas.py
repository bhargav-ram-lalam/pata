"""
api/schemas.py
==============
Pydantic v2 schemas for API requests, responses, batch payloads, health checks,
and the Stage 4 human-review loop.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

# Re-use DIGIPIN bounding box for India
INDIA_MIN_LAT = 2.5
INDIA_MAX_LAT = 38.5
INDIA_MIN_LON = 63.5
INDIA_MAX_LON = 99.5


class ResolveRequest(BaseModel):
    """Payload for single address resolution."""
    address: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Raw, unstructured Indian address string (max 500 characters).",
        examples=["Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru 560076"],
    )
    hint_lat: Optional[float] = Field(
        None,
        description="Optional GPS latitude hint (within India bounding box: 2.5 to 38.5).",
        examples=[12.9716],
    )
    hint_lng: Optional[float] = Field(
        None,
        description="Optional GPS longitude hint (within India bounding box: 63.5 to 99.5).",
        examples=[77.5946],
    )

    @field_validator("address")
    @classmethod
    def validate_address_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Address cannot be empty or whitespace-only.")
        return stripped

    @field_validator("hint_lat")
    @classmethod
    def validate_hint_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (INDIA_MIN_LAT <= v <= INDIA_MAX_LAT):
            raise ValueError(f"hint_lat {v} is outside India bounding box [{INDIA_MIN_LAT}, {INDIA_MAX_LAT}]")
        return v

    @field_validator("hint_lng")
    @classmethod
    def validate_hint_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (INDIA_MIN_LON <= v <= INDIA_MAX_LON):
            raise ValueError(f"hint_lng {v} is outside India bounding box [{INDIA_MIN_LON}, {INDIA_MAX_LON}]")
        return v


class BatchResolveRequest(BaseModel):
    """Payload for batch address resolution (up to 100 items)."""
    addresses: List[ResolveRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of address resolution requests (max 100 items per batch).",
    )


class BatchItemResult(BaseModel):
    """Individual item result within a batch response."""
    index: int
    success: bool
    request_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BatchResolveResponse(BaseModel):
    """Batch resolution response with per-item success/failure breakdown."""
    total: int
    successful: int
    failed: int
    results: List[BatchItemResult]


class HealthComponentStatus(BaseModel):
    """Status of an individual health check subsystem."""
    status: str  # "healthy" | "degraded" | "unhealthy"
    latency_ms: Optional[float] = None
    details: Optional[str] = None


class HealthResponse(BaseModel):
    """System health check summary."""
    status: str  # "healthy" | "degraded" | "unhealthy"
    version: str
    components: Dict[str, HealthComponentStatus]


# ---------------------------------------------------------------------------
# Stage 4: Human-Review Loop Schemas
# ---------------------------------------------------------------------------

class ReviewQueueItem(BaseModel):
    """A single resolution record in the human-review queue."""
    request_id: str
    confidence: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    parsed: Dict[str, Any]
    digipin: Optional[str] = None
    anchor_type: Optional[str] = Field(
        None,
        description="Geographic anchor type: 'landmark' | 'pincode_centroid' | 'osm_geocode' | 'unresolved'",
    )
    accuracy_radius_meters: Optional[int] = Field(
        None,
        description="Approximate spatial accuracy radius in meters",
    )
    evidence: Dict[str, Any]
    review_status: str
    created_at: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    """Paginated response for GET /v1/review/queue."""
    total: int
    page: int
    page_size: int
    pages: int
    items: List[ReviewQueueItem]


class ConfirmRequest(BaseModel):
    """Payload for POST /v1/review/{request_id}/confirm."""
    reviewer_id: Optional[str] = Field(
        None,
        description="Identifier of the human reviewer (e.g. employee ID or username).",
        examples=["reviewer_007"],
    )


class CorrectRequest(BaseModel):
    """Payload for POST /v1/review/{request_id}/resolve — submit a human correction."""
    reviewer_id: str = Field(
        ...,
        description="Identifier of the human reviewer.",
        examples=["reviewer_007"],
    )
    corrected_lat: Optional[float] = Field(
        None,
        description="Corrected latitude (if location was wrong).",
        examples=[12.9801],
    )
    corrected_lng: Optional[float] = Field(
        None,
        description="Corrected longitude (if location was wrong).",
        examples=[77.5900],
    )
    corrected_parsed: Optional[Dict[str, Any]] = Field(
        None,
        description="Corrected structured address fields (if parsing was wrong).",
        examples=[{"landmark": "Apollo Hospital", "locality": "Bannerghatta Road"}],
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional reviewer notes explaining the correction.",
    )

    @field_validator("corrected_lat")
    @classmethod
    def validate_corrected_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (INDIA_MIN_LAT <= v <= INDIA_MAX_LAT):
            raise ValueError(f"corrected_lat {v} is outside India bounding box")
        return v

    @field_validator("corrected_lng")
    @classmethod
    def validate_corrected_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (INDIA_MIN_LON <= v <= INDIA_MAX_LON):
            raise ValueError(f"corrected_lng {v} is outside India bounding box")
        return v
