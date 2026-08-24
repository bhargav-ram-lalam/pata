"""
api/main.py
===========
FastAPI application for Pata AI address resolution service.
Implements single and batch resolution, persistence, metrics, health probes, and resilience.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from api.auth import get_api_key
from api.review import router as review_router
from api.schemas import (
    ResolveRequest,
    BatchResolveRequest,
    BatchResolveResponse,
    BatchItemResult,
    HealthResponse,
    HealthComponentStatus,
)
from observability.logger import setup_structured_logging, get_logger, request_id_var
from observability.metrics import get_metrics_output
from persistence.database import init_db, get_db_session
from persistence.purge_job import purge_worker
from persistence.repository import save_resolution, get_resolution_by_id
from pipeline import resolve_address, preload_models, AddressResolution

logger = get_logger("pata.api")

# Configuration from environment
REQUEST_TIMEOUT_SEC = float(os.getenv("PATA_REQUEST_TIMEOUT_SEC", "5.0"))
MAX_BATCH_CONCURRENCY = int(os.getenv("PATA_MAX_BATCH_CONCURRENCY", "10"))
CORS_ORIGINS_ENV = os.getenv("PATA_CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_ENV.split(",") if origin.strip()]

_is_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes database, preloads models, and starts background workers."""
    global _is_ready
    setup_structured_logging()
    logger.info("Initializing Pata database and preloading models...")

    try:
        init_db()
        # Preload models synchronously so the first request has zero cold start latency
        preload_models()
        purge_worker.start()
        _is_ready = True
        logger.info("Pata API service successfully initialized and ready to serve traffic.")
    except Exception as exc:
        logger.error("Failed during startup initialization: %s", exc)
        _is_ready = False

    yield

    logger.info("Shutting down Pata API service...")
    await purge_worker.stop()
    logger.info("Pata API shutdown complete.")


app = FastAPI(
    title="Pata Address Resolution API",
    description="AI-powered address resolution & standardization for Indian last-mile logistics.",
    version="0.4.0",
    lifespan=lifespan,
)

# Stage 4: Human-review loop endpoints
app.include_router(review_router)

# ---------------------------------------------------------------------------
# CORS & Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Extract or generate X-Request-ID and inject into context and response headers."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_var.set(req_id)
    t0 = time.perf_counter()

    try:
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
    finally:
        request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/v1/resolve",
    response_model=AddressResolution,
    summary="Resolve a single Indian address",
    dependencies=[Depends(get_api_key)],
)
async def resolve_single_address(
    req: ResolveRequest,
    db: Session = Depends(get_db_session),
):
    """
    Resolve an unstructured Indian address string into a standardized, deliverable geocoded output.
    """
    req_id = request_id_var.get() or str(uuid.uuid4())

    async def _execute_pipeline():
        # Run the CPU/network pipeline in thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: resolve_address(
                req.address,
                request_id=req_id,
                hint_lat=req.hint_lat,
                hint_lng=req.hint_lng,
            ),
        )

    try:
        resolution = await asyncio.wait_for(_execute_pipeline(), timeout=REQUEST_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        logger.warning("Request %s exceeded global timeout of %.1fs — degrading gracefully", req_id, REQUEST_TIMEOUT_SEC)
        # Fallback: run deterministic parser only (sub-millisecond) and flag for human review
        from agents.agent1_parser import DeterministicParserAgent
        a1 = DeterministicParserAgent()
        a1_res, a1_tr = a1.run(req.address, geocode=True)

        resolution = AddressResolution(
            raw_address=req.address,
            parsed=a1_res.to_dict(),
            digipin=a1_res.digipin,
            latitude=a1_res.latitude,
            longitude=a1_res.longitude,
            confidence=round(a1_res.raw_confidence * 0.5, 3),
            needs_human_review=True,
            evidence={
                "timeout": f"Global pipeline timeout exceeded ({REQUEST_TIMEOUT_SEC}s)",
                "agent1_confidence": a1_res.raw_confidence,
                "request_id": req_id,
            },
            pipeline_trace=[a1_tr, {"agent": "GlobalTimeoutFallback", "latency_ms": REQUEST_TIMEOUT_SEC * 1000, "ran": True}],
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ttl_for_raw_retention=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 86400)),
        )

    # Atomically persist in DB
    try:
        save_resolution(db, req_id, resolution, req.address)
    except Exception as exc:
        logger.error("Failed to persist resolution for request %s: %s", req_id, exc)

    return resolution


@app.post(
    "/v1/resolve/batch",
    response_model=BatchResolveResponse,
    summary="Resolve a batch of addresses concurrently",
    dependencies=[Depends(get_api_key)],
)
async def resolve_batch_addresses(
    batch_req: BatchResolveRequest,
    db: Session = Depends(get_db_session),
):
    """
    Process up to 100 addresses concurrently with bounded concurrency.
    Individual failures do not fail the entire batch.
    """
    semaphore = asyncio.Semaphore(MAX_BATCH_CONCURRENCY)

    async def _process_item(index: int, item: ResolveRequest) -> BatchItemResult:
        item_req_id = str(uuid.uuid4())
        async with semaphore:
            try:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(
                    None,
                    lambda: resolve_address(
                        item.address,
                        request_id=item_req_id,
                        hint_lat=item.hint_lat,
                        hint_lng=item.hint_lng,
                    ),
                )
                save_resolution(db, item_req_id, res, item.address)
                res_dict = res.model_dump() if hasattr(res, "model_dump") else res.dict()
                return BatchItemResult(
                    index=index,
                    success=True,
                    request_id=item_req_id,
                    result=res_dict,
                )
            except Exception as exc:
                logger.error("Batch item %d failed: %s", index, exc)
                return BatchItemResult(
                    index=index,
                    success=False,
                    request_id=item_req_id,
                    error=str(exc),
                )

    tasks = [_process_item(i, item) for i, item in enumerate(batch_req.addresses)]
    results = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    return BatchResolveResponse(
        total=len(results),
        successful=successful,
        failed=failed,
        results=results,
    )


@app.get(
    "/v1/resolve/{request_id}",
    summary="Fetch a past non-PII resolution record",
    dependencies=[Depends(get_api_key)],
)
async def get_resolution(
    request_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Retrieve stored non-PII resolution metadata by request_id.
    """
    record = get_resolution_by_id(db, request_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resolution with request_id '{request_id}' not found.",
        )
    return record


@app.get(
    "/v1/health",
    response_model=HealthResponse,
    summary="Detailed subsystem health check",
    dependencies=[Depends(get_api_key)],
)
async def health_check():
    """
    Inspect individual subsystem health: parser, IndicBERT model, Overpass, and LLM key.
    """
    components: Dict[str, HealthComponentStatus] = {}
    overall_healthy = True

    # 1. Check bharataddress parser
    try:
        t0 = time.perf_counter()
        import bharataddress as ba
        ba.parse("560001 Bangalore")
        lat_ms = (time.perf_counter() - t0) * 1000
        components["bharataddress_parser"] = HealthComponentStatus(
            status="healthy",
            latency_ms=round(lat_ms, 2),
            details="Pincode directory and deterministic parser functional.",
        )
    except Exception as e:
        overall_healthy = False
        components["bharataddress_parser"] = HealthComponentStatus(
            status="unhealthy",
            details=f"Parser error: {e}",
        )

    # 2. Check IndicBERT model
    try:
        from pipeline import _agent2
        if _agent2 is not None and _agent2._model is not None:
            components["indicbert_ner_model"] = HealthComponentStatus(
                status="healthy",
                details="Model loaded in memory and ready for inference.",
            )
        else:
            components["indicbert_ner_model"] = HealthComponentStatus(
                status="degraded",
                details="Model not yet warmed in memory.",
            )
    except Exception as e:
        components["indicbert_ner_model"] = HealthComponentStatus(
            status="unhealthy",
            details=f"Model check error: {e}",
        )

    # 3. Check Overpass API (non-blocking short probe)
    try:
        from resilience.overpass_client import overpass_circuit_breaker
        cb_state = overpass_circuit_breaker.state.value
        components["overpass_api"] = HealthComponentStatus(
            status="healthy" if cb_state == "CLOSED" else "degraded",
            details=f"Circuit breaker state: {cb_state}",
        )
    except Exception as e:
        components["overpass_api"] = HealthComponentStatus(
            status="unhealthy",
            details=f"Circuit check error: {e}",
        )

    # 4. Check LLM Provider Configuration
    provider = os.getenv("PATA_LLM_PROVIDER", "anthropic").lower()
    key_var_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    required_key = key_var_map.get(provider, "LLM_API_KEY")
    key_present = bool(os.getenv(required_key))

    components["llm_provider"] = HealthComponentStatus(
        status="healthy" if key_present else "degraded",
        details=f"Provider: {provider}, Key '{required_key}' configured: {key_present}",
    )

    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        version="0.4.0",
        components=components,
    )


@app.get(
    "/v1/health/live",
    summary="Liveness probe for container orchestration",
)
async def health_live():
    """Returns 200 if the process is alive (unauthenticated)."""
    return {"status": "live"}


@app.get(
    "/v1/health/ready",
    summary="Readiness probe for container orchestration",
)
async def health_ready():
    """Returns 200 if models and DB are ready, 503 during warmup (unauthenticated)."""
    if _is_ready:
        return {"status": "ready"}
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Service is initializing / warming up models.",
    )


@app.get(
    "/v1/metrics",
    summary="Prometheus metrics exposition endpoint",
)
async def metrics():
    """Expose Prometheus telemetry metrics."""
    data, content_type = get_metrics_output()
    return Response(content=data, media_type=content_type)
