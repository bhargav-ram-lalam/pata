# Pata (पता) — Business Pitch

*One-page brief for judges and partners. Technical details are in [`PIPELINE.md`](../PIPELINE.md) and [`docs/architecture.md`](architecture.md).*

---

## The Problem

India's e-commerce sector processes over 100 million orders a month. Return-to-origin (RTO) rates — packages that fail delivery and come back — sit between 20–40% for many sellers. A significant fraction of those failures trace back to a single root cause: **the delivery address cannot be resolved to a precise location**.

Indian addresses are fundamentally different from Western ones. They are landmark-centric (*"behind Hanuman Mandir, opposite the yellow water tank"*), written in Hinglish or Devanagari script, missing pincodes, or simply colloquial. Standard geocoding tools — Google Maps, Mapbox, HERE — are built for street-numbered Western addresses. They silently return null or, worse, a plausible-but-wrong coordinate for addresses like these. Each failed delivery costs a seller ₹150–₹300 in reverse logistics. At scale, that is crores of rupees per month in preventable waste.

---

## What Pata Does

Pata is a **selective, cost-aware AI address resolution engine** built from the ground up for India. Given a messy raw address string, it returns a verified coordinate, a structured address hierarchy, a DIGIPIN code, and a confidence score — with a clearly reasoned audit trail explaining what each agent found and why.

Three things make it different:

1. **Evidence-backed, not silent-guessing.** If Pata cannot resolve an address with sufficient confidence, it flags `needs_human_review = true` and routes it to an ops queue. It never fabricates a coordinate. Agents 1–3 can confirm or contradict each other; only when they agree does the system commit.

2. **Cost-aware routing.** Five agents run in sequence, but most work is done by the first three (a deterministic postal parser, a local IndicBERT NER model, and the free OpenStreetMap Overpass API). Only 5–15% of addresses need the LLM disambiguation call in Agent 4. The rest resolve for zero LLM cost.

3. **DIGIPIN as a first-class output.** Every verified address produces a DIGIPIN — India Post's new 10-character national geocode standard. This is immediately usable for last-mile logistics routing and interoperates with India Post's infrastructure.

---

## Measured Cost — Precise Figures

All numbers below come from the Stage 3/4 benchmark runs. Nothing is estimated.

| Agent | Cost | When runs |
|---|---|---|
| A1 — Deterministic Parser | **$0** | 100% of requests |
| A2 — IndicBERT NER | **$0** (local model) | ~35–60% of requests |
| A3 — OSM Overpass | **$0** (free API) | ~20–40% of requests |
| A4 — Rules arbitration | **$0** | 100% of requests |
| A4 — LLM disambiguation | **~$0.00015/call** (Claude Haiku, ~300 tokens) | ~5–15% of requests |
| A5 — Self-Check | **$0** | 100% of requests |

**Benchmark result (15-address gold set):** Total cost = $0.000070 → **$0.0000047 per address** fully loaded.

**At scale (10% LLM trigger rate):**

| Monthly volume | LLM calls | Est. monthly LLM cost |
|---|---|---|
| 100,000 orders | ~10,000 | ~$1.50 |
| **1,000,000 orders** | **~100,000** | **~$15.00** |
| 10,000,000 orders | ~1,000,000 | ~$150.00 |

At 1 million orders per month, the entire AI disambiguation stack costs **$15/month**. If that prevents even 1,000 RTOs (0.1% of volume), the avoided reverse-logistics cost is **₹1.5–₹3 lakh/month** against ₹1,200 in LLM spend. The unit economics are compelling at any reasonable RTO-prevention rate.

---

## Value for the Indian Ecosystem

- **For e-commerce sellers:** Fewer RTOs, lower reverse logistics cost, higher NPS from successful first-attempt delivery.
- **For logistics operators:** Reduced exception handling, automated review queue for genuinely ambiguous cases only, DIGIPIN output ready for India Post routing.
- **For India Post / DPDP compliance:** Native DIGIPIN generation in every verified resolution. Full DPDP Act 2023 compliance — raw addresses purged after 24 hours, structured data only in long-term storage.

---

## What's Next

Four concrete next steps, in priority order:

1. **Expand the gold test set** beyond 15 addresses using the built-in `backend/scripts/export_corrections.py` export tool. The review loop is already accumulating human-corrected examples; this is ready to run today.

2. **Production India-region deployment.** The Kubernetes manifests are in the repo (`k8s/`). Next step is deploying to AWS `ap-south-1` (Mumbai) to satisfy the DPDP Act 2023 data residency requirement.

3. **Partner pilot with one e-commerce seller.** Real RTO data from a pilot would replace the projected cost savings with measured ones, which is what a scale conversation requires.

4. **Fine-tune IndicBERT NER on the corrections dataset.** The review loop captures original vs. corrected field values. These corrections are the training signal to improve the model on the specific Indian address patterns most commonly seen in production.

---

*Pata is open-source at [github.com/bhargav-ram-lalam/pata](https://github.com/bhargav-ram-lalam/pata).*
