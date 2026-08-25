# Bugfix & Precision Transparency Notes

## Part A: Review Queue Duplicate Entries Investigation

### 1. Root Cause Analysis
During manual testing, 65 `pending_review` rows accumulated in the Ops Review Dashboard queue at ~12% confidence with "Unknown City".

**Investigation Findings:**
1. **Accumulation of Test Runs & Demo Runs in Local SQLite DB:**
   - The test suites (`test_api.py`, `test_review.py`, batch resolution tests) and repeated manual runs of `seed_demo_data.py` all wrote to the persistent database (`data/pata.db`).
   - Because each resolve request creates a new UUID `request_id`, repeated test/seed runs without database resets accumulated rows over time.
2. **"Unknown City" is a UI Display Fallback, Not Corrupted Stored Data:**
   - In the database `resolutions.parsed`, `city` was correctly stored as `None` (`null` in JSON) for unresolvable benchmark input `"somewhere near the big tree, 3rd house, some locality"`.
   - The UI table (`ReviewQueueTable.tsx`) rendered `item.parsed?.city || 'Unknown City'` as fallback text for `null` city values.
3. **Pipeline Behavior on Sparse / Garbled Input:**
   - The deterministic parser (A1) and IndicBERT NER (A2) properly detect zero valid postal anchors, resulting in `confidence < 0.50`, `needs_human_review = True`, `anchor_type = "unresolved"`, and `city: null`.

### 2. Solutions Implemented
- **Created `backend/scripts/clear_demo_seed_data.py`:** Utility to wipe or clean `pending_review` items between rehearsals and presentations.
- **Updated `backend/scripts/seed_demo_data.py`:**
  - Added `--reset` flag to wipe stale records prior to seeding.
  - Added duplicate detection (`get_existing_pending_queue`) to prevent re-inserting identical benchmark tiers.
- **Added Regression Tests in `backend/tests/test_api.py`:**
  - `test_garbled_address_unresolvable`: Asserts that garbled inputs yield `confidence < 0.50`, `needs_human_review=True`, `anchor_type="unresolved"`, `accuracy_radius_meters=None`, and that `parsed.city` is not corrupted.

---

## Part B: Precision & Anchor-Type Transparency

### 1. Backend Schema & Derivation
- Added `anchor_type` (`"landmark" | "pincode_centroid" | "osm_geocode" | "unresolved"`) and `accuracy_radius_meters` (`int | None`) to:
  - `AddressResolution` (`backend/pipeline.py`)
  - `ReviewQueueItem` (`backend/api/schemas.py`)
  - `pipeline_demo.py` canned benchmark responses
  - `backend/persistence/repository.py` database mapping
- **Accuracy Radii:**
  - Landmark match (Agent 3): **~150m**
  - Pincode centroid fallback (Agent 1): **~2000m**
  - Unresolved: **null**

### 2. Frontend UI Enhancements
- **Leaflet `MapViewer.tsx` (Playground & Review Dashboard):**
  - Renders a translucent accuracy circle (`L.circle`) sized by `accuracy_radius_meters` (tight ~150m cyan circle for landmarks, wide ~2000m amber dashed circle for pincode areas).
  - Displays top overlay badge: `📍 Landmark-anchored (~150m)` or `📮 Pincode-area estimate (~2km) — no landmark match`.
- **`ConfidenceBadge.tsx` Caveat:**
  - When `anchor_type === 'pincode_centroid'`, renders explicit warning: *"No landmark matched — location is an area estimate (~2km radius), not a specific point."*

### 3. Arbitration Scoring Analysis
- **Can a result be HIGH confidence and pincode-centroid anchored?**
  - In `agent4_arbitration.py`, `combined = 0.50*A1 + 0.15*A1_freetext + 0.10*A2 + 0.25*A3`.
  - When no landmark matches (`A3 = 0`), the maximum mathematical score is `0.75`.
  - Because `HIGH_THRESHOLD = 0.80`, pincode-only results can never reach HIGH tier; they land in MEDIUM (or LOW), where pin confirmation or review queue routing is enforced and the 2km area caveat is displayed.
