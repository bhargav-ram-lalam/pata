"""
examples/webhook_notification.py
=================================
HMAC-signed webhook delivery for Pata correction events.

When a human submits a correction via POST /v1/review/{id}/resolve, this
module fires a signed POST to PATA_WEBHOOK_URL so an e-commerce backend can
automatically update an order's delivery address.

Security:
  - Payload is signed with HMAC-SHA256 using PATA_WEBHOOK_SECRET
  - X-Pata-Signature header format: sha256=<hex_digest>
  - X-Pata-Timestamp header for replay-attack protection (receivers should
    reject events older than 5 minutes)

Usage (standalone demo):
  python examples/webhook_notification.py

Usage (programmatic):
  from examples.webhook_notification import fire_correction_webhook
  fire_correction_webhook(request_id=..., corrected_lat=..., ...)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Optional

try:
    import requests as http_requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("PATA_WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("PATA_WEBHOOK_SECRET", "changeme_in_production")
WEBHOOK_TIMEOUT_SEC = float(os.getenv("PATA_WEBHOOK_TIMEOUT_SEC", "5.0"))


def _sign_payload(payload_json: str, timestamp: int, secret: str) -> str:
    """
    Compute HMAC-SHA256 signature.
    Signed string: "{timestamp}.{payload_json}"
    Receivers should verify this to prevent replay attacks.
    """
    signed_str = f"{timestamp}.{payload_json}"
    return hmac.new(
        secret.encode("utf-8"),
        signed_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()  # hmac.new is the correct API (not hmac.HMAC)


def fire_correction_webhook(
    request_id: str,
    original_lat: Optional[float],
    original_lng: Optional[float],
    corrected_lat: Optional[float],
    corrected_lng: Optional[float],
    corrected_parsed: Optional[dict],
    reviewer_id: str,
    webhook_url: Optional[str] = None,
    secret: Optional[str] = None,
) -> bool:
    """
    POST a signed correction event to the configured webhook URL.

    Returns True on success (2xx response), False on failure.
    Never raises — errors are logged so the review endpoint stays responsive.

    Args:
        webhook_url: Override PATA_WEBHOOK_URL (useful in tests)
        secret: Override PATA_WEBHOOK_SECRET (useful in tests)
    """
    url = webhook_url or WEBHOOK_URL
    if not url:
        logger.debug("PATA_WEBHOOK_URL not configured — skipping webhook delivery.")
        return False

    _secret = secret or WEBHOOK_SECRET
    timestamp = int(time.time())

    payload = {
        "event": "correction.submitted",
        "request_id": request_id,
        "reviewer_id": reviewer_id,
        "timestamp": timestamp,
        "original": {
            "latitude": original_lat,
            "longitude": original_lng,
        },
        "corrected": {
            "latitude": corrected_lat,
            "longitude": corrected_lng,
            "parsed": corrected_parsed,
        },
    }

    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    signature = _sign_payload(payload_json, timestamp, _secret)

    headers = {
        "Content-Type": "application/json",
        "X-Pata-Signature": f"sha256={signature}",
        "X-Pata-Timestamp": str(timestamp),
        "X-Pata-Event": "correction.submitted",
        "User-Agent": "Pata-Webhook/0.4.0",
    }

    try:
        if HAS_REQUESTS:
            resp = http_requests.post(
                url,
                data=payload_json.encode("utf-8"),
                headers=headers,
                timeout=WEBHOOK_TIMEOUT_SEC,
            )
            success = 200 <= resp.status_code < 300
        else:
            req = urllib.request.Request(url, data=payload_json.encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SEC) as resp:
                success = 200 <= resp.status < 300

        if success:
            logger.info("Webhook delivered for correction %s → %s", request_id, url)
        else:
            status_code = getattr(resp, "status_code", getattr(resp, "status", "?"))
            logger.warning("Webhook delivery failed for %s — HTTP %s", request_id, status_code)
        return success

    except Exception as exc:
        logger.warning("Webhook delivery error for %s: %s", request_id, exc)
        return False


def verify_webhook_signature(payload_json: str, timestamp: int, signature_header: str, secret: str) -> bool:
    """
    Helper for e-commerce receivers to verify incoming webhook authenticity.

    Args:
        payload_json: Raw JSON body string from the HTTP request
        timestamp: X-Pata-Timestamp header value (int)
        signature_header: X-Pata-Signature header value (e.g. "sha256=abc123...")
        secret: Shared HMAC secret

    Returns:
        True if signature is valid AND event is not older than 5 minutes.

    Example (e-commerce receiver):
        from examples.webhook_notification import verify_webhook_signature
        if not verify_webhook_signature(body, ts, sig, MY_SECRET):
            return Response(status=401)
    """
    # Reject stale events (replay protection)
    if abs(time.time() - timestamp) > 300:
        return False

    expected_sig = _sign_payload(payload_json, timestamp, secret)
    expected_header = f"sha256={expected_sig}"

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature_header, expected_header)


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os as _os
    logging.basicConfig(level=logging.INFO)

    # Demo: set PATA_WEBHOOK_URL to a local test endpoint (e.g. httpbin.org/post)
    demo_url = _os.getenv("PATA_WEBHOOK_URL", "https://httpbin.org/post")

    print(f"\n=== Pata Webhook Notification Demo ===")
    print(f"Sending correction event to: {demo_url}\n")

    success = fire_correction_webhook(
        request_id="demo-request-12345",
        original_lat=12.9716,
        original_lng=77.5946,
        corrected_lat=12.9801,
        corrected_lng=77.5900,
        corrected_parsed={"landmark": "Apollo Hospital", "locality": "Bannerghatta Road", "city": "Bengaluru"},
        reviewer_id="reviewer_001",
        webhook_url=demo_url,
    )

    print(f"Webhook delivery {'✓ succeeded' if success else '✗ failed'}")

    # Demo: signature verification
    ts = int(time.time())
    secret = "demo_secret"
    payload = '{"event":"correction.submitted","request_id":"demo-request-12345"}'
    sig = _sign_payload(payload, ts, secret)
    header = f"sha256={sig}"
    verified = verify_webhook_signature(payload, ts, header, secret)
    print(f"Signature verification: {'✓ valid' if verified else '✗ invalid'}")
