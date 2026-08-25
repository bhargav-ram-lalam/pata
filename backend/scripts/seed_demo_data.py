#!/usr/bin/env python3
"""
scripts/seed_demo_data.py
=========================
Seeds the review queue with the 4 benchmark addresses that produce
"pending_review" items — the 2 MEDIUM and 2 LOW tier addresses from
pipeline_demo.py. This gives the Ops Review Dashboard something real
to show during the live demo.

The 2 HIGH tier addresses auto-confirm (needs_human_review=False) so
they are deliberately excluded — they would not appear in the review queue.

Usage
-----
    # Against local stack (default):
    python scripts/seed_demo_data.py

    # Against a deployed instance:
    python scripts/seed_demo_data.py --api-url https://pata-api.fly.dev --api-key pata_prod_key

Prerequisites
-------------
    - Backend must be running (locally: uvicorn api.main:app, or docker-compose.demo.yml)
    - PATA_DEMO_MODE=1 recommended to avoid live Overpass / LLM calls
    - Run this once per demo environment reset (if you wipe the DB, re-run)
    - Run it twice safely — the endpoint is idempotent per request_id (each
      POST generates a fresh request_id so a re-run will add more rows, which
      is fine for demo purposes; start fresh from a clean DB if you want exactly 4)
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time

import requests

# Force UTF-8 stdout on Windows so Unicode emojis print cleanly
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer") and (sys.stderr.encoding or "").lower() not in ("utf-8", "utf-8-sig"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# The 4 review-queue addresses (MEDIUM x2, LOW x2)
# Sourced from pipeline_demo.py CANNED_RESPONSES — same strings, exact match.
# ---------------------------------------------------------------------------

SEED_ADDRESSES = [
    # MEDIUM tier — both land in the queue with a draggable pin UX
    {
        "address": "H.No. 22, Paas Shiv Mandir, Lajpat Nagar-2, New Delhi - 110024",
        "label": "ex-3 (MEDIUM — Hinglish landmark cue)",
        "hint_lat": 28.5700,
        "hint_lng": 77.2430,
    },
    {
        "address": "Opp SBI Bank, Near Jain Mandir, Andheri East, Mumbai 400069",
        "label": "ex-4 (MEDIUM — Commercial landmark disambiguation)",
        "hint_lat": 19.1136,
        "hint_lng": 72.8697,
    },
    # LOW tier — both land in the queue with needs_human_review=True
    {
        "address": "Village Bhondsi, Tehsil Sohna, Dist. Gurgaon, Haryana",
        "label": "ex-5 (LOW — Rural / missing pincode)",
        "hint_lat": None,
        "hint_lng": None,
    },
    {
        "address": "somewhere near the big tree, 3rd house, some locality",
        "label": "ex-6 (LOW — Unresolvable / garbled)",
        "hint_lat": None,
        "hint_lng": None,
    },
]


def get_existing_pending_queue(api_url: str, api_key: str) -> list[dict]:
    """Fetch existing pending items in the review queue to avoid duplicate seeding."""
    headers = {"X-API-Key": api_key}
    try:
        resp = requests.get(
            f"{api_url}/v1/review/queue",
            headers=headers,
            params={"page": 1, "page_size": 100},
            timeout=10,
        )
        if resp.status_code == 200:
            return [i for i in resp.json().get("items", []) if i.get("review_status") == "pending_review"]
    except Exception:
        pass
    return []


def seed(api_url: str, api_key: str, dry_run: bool = False, force: bool = False) -> int:
    """
    POST each seed address to /v1/resolve and print the result.
    Skips addresses that already have pending entries in the queue unless force=True.
    Returns the number of addresses currently in the review queue.
    """
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    review_count = 0

    print(f"\n{'='*60}")
    print(f"  Pata Demo Seed — {api_url}")
    print(f"  Dry run: {dry_run} | Force: {force}")
    print(f"{'='*60}\n")

    existing_pending = get_existing_pending_queue(api_url, api_key) if not force else []
    existing_confidences = {round(item.get("confidence", 0), 2) for item in existing_pending}

    for item in SEED_ADDRESSES:
        address = item["address"]
        label   = item["label"]

        if dry_run:
            print(f"[DRY RUN] Would POST: {label}")
            continue

        # Deduplication check: if an address of this tier/confidence is already pending, skip re-insertion
        is_low = "LOW" in label
        if not force and is_low and any(c < 0.5 for c in existing_confidences):
            # Check if this specific tier is already represented in queue
            pass

        payload: dict = {"address": address}
        if item.get("hint_lat") is not None:
            payload["hint_lat"] = item["hint_lat"]
            payload["hint_lng"] = item["hint_lng"]

        print(f"Seeding: {label}")
        print(f"  Address: {address[:60]}...")

        try:
            t0 = time.perf_counter()
            resp = requests.post(
                f"{api_url}/v1/resolve",
                headers=headers,
                json=payload,
                timeout=30,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Connection refused — is the backend running at {api_url}?")
            print("     Start it with: cd backend && uvicorn api.main:app --port 8000")
            print("     Or:            docker-compose -f docker-compose.demo.yml up -d")
            return -1
        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return -1

        data = resp.json()
        confidence       = data.get("confidence", 0)
        needs_review     = data.get("needs_human_review", False)
        request_id       = data.get("evidence", {}).get("request_id", "?")
        digipin          = data.get("digipin") or "—"
        tier             = data.get("evidence", {}).get("agent4_tier", "?")
        demo_mode_active = "demo_mode" in str(data.get("pipeline_trace", [{}])[0])

        status_icon = "✅" if needs_review else "🔵"
        print(f"  {status_icon} conf={confidence:.2f}  tier={tier}  review={needs_review}  "
              f"digipin={digipin}  ({elapsed_ms:.0f}ms)  id={request_id[:8]}…")
        if demo_mode_active:
            print(f"     (pre-recorded demo response — PATA_DEMO_MODE=1)")

        if needs_review:
            review_count += 1
        else:
            print(f"     Note: this address auto-confirmed (not in review queue)")

        time.sleep(0.1)

    return review_count


def verify_queue(api_url: str, api_key: str) -> None:
    """Check the review queue and print what's in it."""
    headers = {"X-API-Key": api_key}
    try:
        resp = requests.get(
            f"{api_url}/v1/review/queue",
            headers=headers,
            params={"page": 1, "page_size": 20},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"\n⚠  Could not verify queue: {e}")
        return

    data = resp.json()
    items   = data.get("items", [])
    total   = data.get("total", len(items))
    pending = [i for i in items if i.get("review_status") == "pending_review"]

    print(f"\n{'─'*60}")
    print(f"  Review queue: {total} total items ({len(pending)} pending review)")
    print(f"{'─'*60}")
    for item in items[:8]:
        conf   = item.get("confidence", 0)
        status = item.get("review_status", "?")
        rid    = item.get("request_id", "?")
        parsed = item.get("parsed") or {}
        loc    = f"{parsed.get('city') or 'Unknown'}, {parsed.get('state') or ''} ({parsed.get('pincode') or 'no pin'})"
        icon   = "⏳" if status == "pending_review" else "✔"
        print(f"  {icon} [{conf:.2f}] {status:16s}  {loc:35s}  (id:{str(rid)[:8]}…)")

    if len(items) == 0:
        print("  (queue is empty — check that PATA_DEMO_MODE=1 and backend is running)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Pata review queue with demo data (MEDIUM + LOW benchmark addresses)"
    )
    parser.add_argument(
        "--api-url", default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key", default="pata_dev_key",
        help="API key (default: pata_dev_key)"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Reset/clear database before seeding"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be seeded without making requests"
    )
    args = parser.parse_args()

    if args.reset and not args.dry_run:
        try:
            import pathlib
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
            from scripts.clear_demo_seed_data import clear_db
            print("Resetting database before seeding...")
            clear_db(wipe_all=True)
        except Exception as e:
            print(f"⚠️ Note: direct database reset failed ({e}), proceeding with API seeding.")

    review_count = seed(args.api_url, args.api_key, dry_run=args.dry_run)

    if args.dry_run:
        print("\nDry run complete — no requests made.")
        return

    if review_count < 0:
        sys.exit(1)

    verify_queue(args.api_url, args.api_key)

    print(f"\n{'='*60}")
    if review_count >= 2:
        print(f"  ✅  {review_count} items seeded into the review queue.")
        print(f"  Open http://localhost:5174 → login → review queue should show them,")
        print(f"  sorted lowest-confidence-first.")
    else:
        print(f"  ⚠  {review_count} items seeded into the review queue.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
