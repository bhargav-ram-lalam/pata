# Pata (पता) — 8-Minute Live Demo Script

> **Purpose:** Minute-by-minute walkthrough for the live hackathon demo. Use this to rehearse. In the worst case (projector issues, nerves) it can be read from directly. It is also the voiceover script for a pre-recorded backup video.
>
> **Setup before taking the stage:**
> 1. Run `bash backend/scripts/preflight_check.sh` — all 9 checks must be ✅
> 2. **Seed the review queue** (required for the dashboard demo — run once per fresh environment):
>    ```bash
>    PATA_DEMO_MODE=1 python backend/scripts/seed_demo_data.py
>    ```
>    Confirm you see "2 MEDIUM + 2 LOW items seeded" and the queue shows them sorted lowest-confidence-first.
> 3. Browser tabs pre-opened: `http://localhost:5173` (Playground), `http://localhost:5174` (Dashboard)
> 4. API key `pata_dev_key` typed into the dashboard login field but not yet submitted
> 5. Demo Mode confirmed active (`PATA_DEMO_MODE=1`) — benchmark addresses resolve from pre-recorded responses even without network

---

## 0:00 – 0:45 · The Problem

**[Slide or spoken — no typing yet]**

> "India processes over 100 million e-commerce orders every month. About 20–40% of them come back as RTOs — returns to origin — costing ₹150 to ₹300 per package in reverse logistics. The root cause for a significant fraction of those RTOs is an undeliverable address.
>
> Here's a real one: *'Paas Shiv Mandir, H.No. 22, Lajpat Nagar-2, New Delhi.'* 'Paas' is Hindi for 'near'. Google Maps doesn't know that. Standard geocoders return null. The delivery executive makes a phone call, wastes 10 minutes, or just marks it failed.
>
> Pata solves this. It's a 5-agent AI pipeline that understands Indian addresses the way a local does — phonetic aliases, Devanagari script, Hinglish cues, landmark-centric descriptions — and gives back a verified coordinate, a confidence score, and a DIGIPIN code. All for under a fraction of a rupee per address."

---

## 0:45 – 2:00 · HIGH-Tier Resolution (clean address)

**[Switch to browser: Playground at http://localhost:5173]**

> "Let me show you how it works with a clean, well-formed address first."

**ACTION:** In the benchmark carousel, click **"Clean Landmark & Pincode"** (ex-1: Apollo Hospital, Bengaluru 560076)

> "The pipeline starts immediately. Watch the agent trace light up from left to right."

**Point to the Live Trace panel as agents complete:**
- Agent 1 fires in < 1ms — "Deterministic postal parser extracts pincode 560076, maps to Bengaluru Urban, Karnataka."
- Agent 2 fires in ~50ms — "IndicBERT NER — this is a local language model, not a cloud call — extracts 'Apollo Hospital' as landmark."
- Agent 3 fires in ~300ms — "Queries OpenStreetMap's Overpass API, finds the hospital POI by phonetic match, returns the precise GPS coordinate."
- Agent 4 in < 1ms — "Confidence arbitration: 0.87, HIGH tier. No LLM call needed — that's why it's so cheap."
- Agent 5 in ~1ms — "Self-check: coordinate is within the pincode radius. DIGIPIN generated."

**Point to the confidence badge:**
> "GREEN banner — HIGH tier, auto-confirmed for shipping. No human touches this order."

**Point to DIGIPIN card:**
> "This 10-character code is India Post's new national geolocation standard. Pata generates it from the resolved coordinate. Every verified address gets one."

---

## 2:00 – 3:30 · MEDIUM-Tier — Hinglish Address + Pin Confirmation

**[Stay in Playground]**

> "Now the interesting case — a Hinglish address with an abbreviation and a colloquial cue."

**ACTION:** Click **"Hinglish Cue & Abbreviation"** (ex-3: H.No. 22, Paas Shiv Mandir, Lajpat Nagar-2, New Delhi - 110024)

> "Watch Agent 2 trigger. 'H.No.' is a building prefix abbreviation, 'Paas' is a Hinglish proximity cue — the NER model handles both. Agent 4 lands in the MEDIUM confidence band, so it makes one LLM call for disambiguation."

**Point to the Agent 4 trace (shows LLM latency ~600ms):**
> "One call to Claude Haiku — scoped prompt with the two parse candidates and the nearest OSM POI. It responds in under a second with a JSON choice."

**Point to the AMBER banner:**
> "AMBER banner. The system knows it's not certain enough to auto-confirm. Instead, it enables the draggable pin. Let me show you the human-in-the-loop."

**ACTION:** Drag the map pin a few streets over, then click **"Confirm Location"**

> "The delivery executive can drag the pin to the exact house, click Confirm — that posts to the review API and fires a signed webhook to the e-commerce backend. The corrected coordinate is stored as a training example for the next round of fine-tuning."

---

## 3:30 – 4:30 · LOW-Tier — Unresolvable Address

**ACTION:** Click **"Unresolvable / Garbled Landmark"** (ex-6: "somewhere near the big tree, 3rd house, some locality")

> "This is a deliberately vague address. No pincode, no city, no identifiable POI. Watch what Pata does NOT do: it does not guess silently. No made-up coordinate."

**Point to the RED banner:**
> "RED banner — needs human review. The Self-Check agent in Agent 5 flagged it as undeliverable and routed it to the ops review queue. The order is held, not shipped to the wrong location."

> "That flag is what separates Pata from a system that would silently return a random coordinate and cause an RTO."

---

## 4:30 – 5:30 · Ops Review Dashboard

**[Switch to browser tab: Dashboard at http://localhost:5174]**

> "This is the Ops Review Dashboard — the other half of the product."

**ACTION:** Submit login with API key `pata_dev_key` if not already logged in.

**Point to the Telemetry Header:**
> "Live Prometheus metrics scraped from the backend — review queue size, confirmations, corrections, average turnaround time."

**ACTION:** Find the Shiv Mandir item (confirmed from the MEDIUM demo), click to open the drawer.

> "The reviewer sees the resolved coordinate on a map, the raw address, all structured fields, and a full evidence trail. They can confirm the machine's answer or submit a correction with their own coordinates."

**[If the item is there, click Confirm; if not, point to any pending item]**

> "Confirmed. That fires back to the webhook. In a production integration, the e-commerce platform updates the shipment record in real time."

---

## 5:30 – 6:30 · Architecture & Cost

**[Switch to slides or open `docs/architecture.md` in browser — GitHub renders Mermaid]**

> "Three diagrams tell the full story."

**Diagram 1 — Pipeline Flow:**
> "Five agents. The first three are zero-cost — deterministic rules, a local IndicBERT model, and the free OpenStreetMap API. Only Agent 4 can call an LLM, and only for the 5–15% of addresses in the MEDIUM confidence band. The remaining 85–95% never touch the LLM at all."

**Diagram 2 — Full-Stack View:**
> "Two frontends, one FastAPI backend, Postgres + Redis for state, with a feedback loop from the review dashboard back to a corrections dataset that can be used for fine-tuning."

**Cost slide or PIPELINE.md cost table:**
> "Measured on our 15-address benchmark: $0.000070 total — $0.0000047 per address fully loaded. At 1 million orders per month, LLM cost is $15. Not $15,000. Fifteen dollars. Agents 1, 2, 3, and 5 are literally free."

---

## 6:30 – 7:30 · Pitch — DPDP, DIGIPIN, What's Next

> "Two compliance features that matter for India specifically."

> "First: DPDP Act 2023. Raw address strings are personal data under Indian law. Pata stores them in a staging table with an automated 24-hour purge worker. Long-term storage holds only structured coordinates and DIGIPIN — no PII. There's a machine-enforceable TTL field in every API response so consumers can't forget to purge."

> "Second: DIGIPIN. India Post launched this standard in 2024. Every verified address in Pata generates a DIGIPIN — a 10-character geocode tied to a 4m × 4m grid cell. We're the first address resolution system we know of to generate DIGIPIN as a standard output field."

**What's next:**
> "Four concrete next steps: one — expand the gold test set beyond 15 addresses using the export script built into the review loop. Two — production deployment in an India AWS region for DPDP compliance. Three — a partner pilot with one e-commerce seller to measure RTO impact with real data. Four — fine-tune the IndicBERT NER model on the corrections dataset accumulating in the review loop."

---

## 7:30 – 8:00 · Q&A Seeds

> "Happy to go deeper on any of this. A few questions I can anticipate:"

**"How do you handle Devanagari script?"**
> Agent 1 uses the `indic-transliteration` library to detect and normalise Devanagari before parsing. Agent 2's IndicBERT model was pre-trained on multilingual Indian text and handles Devanagari natively. Both paths are tested in the 15-address benchmark.

**"What's the real RTO cost saving?"**
> We don't have live production data yet — that's what the partner pilot is for. But the breakeven is straightforward: if Pata costs $15/month at 1M orders and prevents even 1,000 RTOs (0.1% of volume), the savings are ₹1.5–3 lakh/month against ₹1,200 in LLM spend. The math works by orders of magnitude.

**"Why isn't the pin exact on every address / How do you communicate accuracy?"**
> Pata distinguishes between landmark-anchored coordinates (~150m accuracy radius) and postal centroid area estimates (~2000m radius). The API exposes explicit `anchor_type` and `accuracy_radius_meters` fields, and the UI visually renders translucent accuracy circles around each pin. If no landmark matches, we show an explicit area estimate caveat rather than claiming false rooftop precision.

**"Why not just use Google Maps Geocoding?"**
> Google Maps Geocoding does not handle landmark-centric Indian addresses reliably (common known limitation). It also returns a coordinate only — no confidence score, no human-review flag, no DIGIPIN, no DPDP-compliant data retention. Pata is designed for the India-specific problem from the ground up.

**"Is this production-ready?"**
> The pipeline is fully tested (31 tests across API, resilience, pipeline, and review loop). The Kubernetes deployment manifests are in the repo (HPA min 2 / max 10 replicas). What's missing is a production deployment — which is the next step we'd do with a seed pilot partner.

---

## Checklist for the Day Of

**Environment setup (≥30 min before the demo)**
- [ ] `bash backend/scripts/preflight_check.sh` — all 9 checks ✅
- [ ] `PATA_DEMO_MODE=1 python backend/scripts/seed_demo_data.py` — confirm "4 items seeded" output
- [ ] Open dashboard → login → verify review queue shows ≥2 pending items, sorted by confidence ascending
- [ ] `PATA_DEMO_MODE=1` confirmed in environment (or set in shell: `export PATA_DEMO_MODE=1`)

**Browser / presentation**
- [ ] Browser tabs open: `localhost:5173`, `localhost:5174`
- [ ] API key pre-typed in dashboard login field (not yet submitted)
- [ ] Architecture slide / `docs/architecture.md` tab ready
- [ ] Cost table (PIPELINE.md or slide) ready

**Backup plan**
- [ ] Phone hotspot ready if venue WiFi drops
- [ ] `PATA_DEMO_MODE=1` guarantees benchmark addresses resolve even offline
- [ ] Presenter notes on phone for Q&A reference
