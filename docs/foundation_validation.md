# Pata Stage 1 — Foundation Validation & Benchmark Report

**Status:** Stage 1 — Foundation Validation Complete  
**Date:** August 2026  
**Repository:** `pata` (AI Address Resolution System for Indian Last-Mile Delivery)

---

## 1. Environment & Installed Versions

| Component / Dependency | Installed Version | Notes / Extras |
| :--- | :--- | :--- |
| **Python Runtime** | `3.13.5` | Standard CPython (64-bit on Windows) |
| **`bharataddress`** | `0.4.0` | Rule-based parser, India Post validator, DIGIPIN & offline centroids |
| **`indic_transliteration`** | `2.3.82` | `bharataddress[indic]` extra (Devanagari / Indic script support) |
| **`RapidFuzz`** | `3.14.5` | `bharataddress[fuzzy]` extra (Phonetic matching accelerator) |
| **`transformers`** | `5.14.1` | Hugging Face Transformers pipeline & token classification |
| **`torch`** | `2.13.0+cpu` | PyTorch CPU runtime (CUDA unavailable in sandbox) |
| **`pydantic`** | `2.13.4` | Data modeling & schema contracts |
| **`pytest`** | `9.1.1` | Test suite runner |

---

## 2. Measured Latency & Resource Benchmarks

### 2.1 `bharataddress` Parsing Benchmark (50 Iterations)
*Benchmark Address:* `"Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru, Karnataka 560076"`

| Metric | Measured Value | Documented Claim | Observation |
| :--- | :--- | :--- | :--- |
| **Mean Latency** | **`0.183 ms`** | `~5.0 ms` | **~27x faster** than claimed (pure in-memory regex & hash lookups) |
| **Median Latency** | **`0.153 ms`** | — | Consistent sub-millisecond execution |
| **Min Latency** | **`0.146 ms`** | — | Cache-warmed execution baseline |
| **Max Latency** | **`0.426 ms`** | — | Negligible jitter |
| **P95 Latency** | **`0.368 ms`** | — | Highly deterministic SLAs |

### 2.2 IndicBERT NER Model Benchmark (`shiprocket-ai/open-indicbert-indian-address-ner`)
*Hardware:* CPU Execution (No GPU available)

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Model Size / Params** | **`32,870,679 params (~125.4 MB)`** | Compact Albert/IndicBERT backbone |
| **Cold Load Time** | **`4.63 s – 4.82 s`** | AutoTokenizer + AutoModelForTokenClassification weight load |
| **Mean Inference Latency** | **`42.42 ms`** | Measured over 10 repeated inferences on CPU |
| **Median Inference Latency** | **`40.83 ms`** | Predictable CPU throughput (~24 requests/sec per core) |
| **Min / Max Latency** | **`38.84 ms / 55.70 ms`** | Low CPU variance |

---

## 3. Side-by-Side Field Extraction Matrix

To establish the empirical basis for Stage 2 agent orchestration and field ownership, the same 6 diverse address archetypes were evaluated across both foundation libraries.

```
Model Label Schemas:
• bharataddress: building_number, building_name, landmark, locality, sub_locality, city, district, state, pincode, digipin, latitude, longitude
• IndicBERT:     house_details, building_name, landmarks, road, locality, sub_locality, floor, city, state, pincode, country
```

### Address 1: Standard Structured Address
> **Raw:** `"Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru, Karnataka 560076"`

| Field | `bharataddress` Output | `IndicBERT` Output | Analysis & Ownership Insight |
| :--- | :--- | :--- | :--- |
| **Building / House** | `num='402', name='Shanti Heights'` | `house_details='flat 402,' (0.993)`, `building_name='shanti heights,' (0.997)` | **Agreement.** Both cleanly split flat number and building name. IndicBERT preserves "Flat". |
| **Landmark** | `landmark='Apollo Hospital'` | `landmarks='near apollo hospital,' (0.979)` | **Agreement.** `bharataddress` strips cue word "Near"; IndicBERT includes span. |
| **Road / Locality** | `locality='Bannerghatta Road'` | `road='bannerghatta road,' (0.990)` | IndicBERT recognizes explicit `road` entity type; `bharataddress` defaults to `locality`. |
| **City** | `'Bangalore'` (via 560076 lookup) | `'bengaluru,' (0.928)` | `bharataddress` canonicalizes to India Post standard; IndicBERT extracts verbatim token. |
| **State** | `'Karnataka'` | `'karnataka' (0.995)` | **Agreement.** |
| **Pincode** | `'560076'` | `'560076' (1.000)` | **Agreement.** |
| **Confidence** | `1.00` | Avg `0.983` | Both high confidence. |

---

### Address 2: Stacked Landmark-Only (No Pincode)
> **Raw:** `"Opposite to City Centre Mall, Behind Chai Point, Near Metro Pillar 124, MG Road, Bengaluru"`

| Field | `bharataddress` Output | `IndicBERT` Output | Analysis & Ownership Insight |
| :--- | :--- | :--- | :--- |
| **Building / House** | `None` | `house_details='124,' (0.474)` | **Discrepancy.** IndicBERT misclassified pillar number "124" as house details due to positional bias. |
| **Landmarks** | `'to City Centre Mall; Chai Point; Metro Pillar 124'` | *Missed / Labeled as 'O'* | **`bharataddress` Wins.** Rule-based cue segmenter (`Opposite`, `Behind`, `Near`) cleanly captures all 3 landmarks. |
| **Road / Locality** | `locality='MG Road'` | `road='mg road,' (0.977)` | Both recognize MG Road. |
| **City** | `'Bengaluru'` | `'bengaluru' (0.792)` | Both capture city. |
| **Pincode** | `None` | `None` | Missing in raw. |
| **Confidence** | `0.40` | Lower token scores | `bharataddress` flags low postal confidence (missing pin). |

---

### Address 3: Complex House Number & S/O Care-Of Format
> **Raw:** `"H.No. 4-12/A, S/O Rama Rao, Near Water Tank, Madhapur, Hyderabad, Telangana 500081"`

| Field | `bharataddress` Output | `IndicBERT` Output | Analysis & Ownership Insight |
| :--- | :--- | :--- | :--- |
| **House Details** | `num='4-12', name='/A'` | `house_details='h.no. 4-12/a,' (0.805)` | **IndicBERT Wins.** `bharataddress` splits compound number "4-12/A" into number "4-12" and building_name "/A". IndicBERT keeps "H.No. 4-12/A" unified. |
| **Care-Of / Residue**| Stripped / Ignored | `building_name='s/o rama rao,' (0.613)` | IndicBERT misidentifies S/O as building_name; `bharataddress` cleaner for postal delivery. |
| **Landmark** | `'Water Tank'` | `landmarks='near water tank,' (0.956)` | **Agreement.** |
| **Locality** | `'Madhapur'` | `locality='madhapur,' (0.989)` | **Agreement.** |
| **City / State / Pin**| `'Hyderabad'`, `'Telangana'`, `'500081'` | `'hyderabad'`, `'telangana'`, `'500081'` | **Agreement.** Full consensus. |

---

### Address 4: Missing Pincode with Floor & Complex Building Details
> **Raw:** `"2nd Floor, Krishna Niwas, Near Old Post Office, Shivaji Nagar, Pune, Maharashtra"`

| Field | `bharataddress` Output | `IndicBERT` Output | Analysis & Ownership Insight |
| :--- | :--- | :--- | :--- |
| **Floor** | `sub_locality='2nd Floor'` | `floor='2nd floor,' (0.991)` | **IndicBERT Wins.** IndicBERT has dedicated `floor` entity. `bharataddress` wrongly places floor in `sub_locality`. |
| **Building Name** | `locality='Krishna niwas'` | `building_name='krishna niwas,' (0.997)` | **IndicBERT Wins.** IndicBERT recognizes named apartment without standard keyword. |
| **Landmark** | `'Old Post Office'` | `landmarks='near old post office,' (0.978)` | Both detect landmark. |
| **Locality** | `None` (misassigned) | `locality='shivaji nagar,' (0.998)` | **IndicBERT Wins.** |
| **City / State** | `city='Maharashtra'`, `state=None` | `city='pune,' (0.996)`, `state='maharashtra' (0.998)` | **IndicBERT Wins.** Without a pincode, `bharataddress` treats trailing "Maharashtra" as `city` and fails on `state`. |

---

### Address 5: Mixed Devanagari (Hindi) & English Script
> **Raw:** `"मकान नं १२, शांति कुंज, near railway station, Jaipur, Rajasthan 302001"`

| Field | `bharataddress` (transliterate=True) | `IndicBERT` Output | Analysis & Ownership Insight |
| :--- | :--- | :--- | :--- |
| **House / Locality** | `locality='makAna naM 12'`, `sub_locality='shAMti kuMja'` | `house_details='मकन न १२,' (0.988)`, `locality='शत कज,' (0.911)` | IndicBERT processes native Devanagari directly. `bharataddress` transliterates to ITRANS Latin before parsing. |
| **Landmark** | `'railway station'` | `landmarks='near railway station,' (0.977)` | Both detect landmark accurately. |
| **City / State / Pin**| `'Jaipur'`, `'Rajasthan'`, `'302001'` | `'jaipur'`, `'rajasthan'`, `'302001'` | **Agreement.** High confidence across both systems. |

---

### Address 6: Colloquial Phrasing with Informal Descriptors
> **Raw:** `"Opposite to red water tank behind chai ki tapri near pipal tree, gali no 4, Sangam Vihar, New Delhi 110080"`

| Field | `bharataddress` Output | `IndicBERT` Output | Analysis & Ownership Insight |
| :--- | :--- | :--- | :--- |
| **Landmark Chain** | `landmark='to red water tank behind chai ki tapri near pipal tree'` | *O (Outside)* | `bharataddress` captures full descriptive landmark string using delimiter rules; IndicBERT under-triggers on long non-standard chains. |
| **Road / Sub-loc** | `sub_locality='gali no 4'` | `road='gali no 4,' (0.967)` | IndicBERT labels "gali no 4" as `road`. `bharataddress` labels it `sub_locality`. |
| **Locality / City** | `locality='Sangam vihar'`, `city='South Delhi'` | `locality='sangam vihar'`, `city='new delhi'` | `bharataddress` uses India Post district for 110080 ("South Delhi"); IndicBERT extracts token ("New Delhi"). |
| **Pincode** | `'110080'` | `'110080' (1.000)` | **Agreement.** |

---

## 4. Stage 2 Field Ownership & Merge Policy Matrix

Based on our empirical validation data, the ownership table for the upcoming Stage 2 Agent pipeline is derived as follows:

| Target Field | Recommended Owner | Fallback / Arbitration Policy | Justification |
| :--- | :--- | :--- | :--- |
| **`pincode`** | **`Agent 1 (bharataddress)`** | IndicBERT NER token | `bharataddress` enforces valid 6-digit regex [1-8]\d{5} and verifies existence against the 154,000+ India Post directory. |
| **`state`** | **`Agent 1 (bharataddress)`** | IndicBERT `state` | When pincode is valid, postal directory lookup guarantees 100% correct official state. If pincode is missing, IndicBERT must take ownership. |
| **`city` / `district`**| **Hybrid (Arbitrated)** | IndicBERT verbatim token | `bharataddress` provides canonical revenue city/district; IndicBERT preserves conversational city names (e.g., "Kochi" vs "Ernakulam"). |
| **`floor`** | **`Agent 2 (IndicBERT)`** | None | `bharataddress` does not have a `floor` slot and misplaces floor tokens into `sub_locality`. |
| **`house_details`**| **`Agent 2 (IndicBERT)`** | `bharataddress` building_number | IndicBERT handles hyphenated, slashed, and alphanumeric apartment codes (e.g. `H.No. 4-12/A`) without over-segmenting. |
| **`building_name`** | **`Agent 2 (IndicBERT)`** | `bharataddress` building_name | IndicBERT recognizes named buildings without mandatory keywords ("Heights", "Towers", "Apartment"). |
| **`road`** | **`Agent 2 (IndicBERT)`** | `bharataddress` locality | Dedicated `road` classification separates street names ("MG Road", "Gali No 4") from neighborhood names. |
| **`landmarks`** | **Dual-Extraction** | Cross-verification in Agent 3 | Use `bharataddress` cue-segmenter for leading spatial clauses (`Opposite to...`) + IndicBERT for descriptive embedded landmarks (`near old post office`). |
| **`digipin` & Coords**| **`Agent 1 / Agent 5`** | OpenStreetMap / Overpass | Deterministic offline math for DIGIPIN and India Post centroid cache. |

---

## 5. Discoveries, Nuances & Deviations from Documentation

1. **`bharataddress.geocode()` Signature:**
   * *Doc implication:* Suggests passing an address string or pincode directly.
   * *Actual implementation:* `geocode(parsed: ParsedAddress, *, online=False)` strictly requires a `ParsedAddress` object. Passing a string throws `AttributeError: 'str' object has no attribute 'pincode'`.
2. **Missing Pincode State Failure in `bharataddress`:**
   * When an address lacks a pincode, `bharataddress` treats the final plain token as `city` and leaves `state` empty, causing addresses like `"... Shivaji Nagar, Pune, Maharashtra"` to set `city='Maharashtra'` and `state=None`.
3. **Pincode Lookup Auto-Override:**
   * When a valid pincode is extracted, `bharataddress` automatically populates `state`, `district`, and `city` from India Post records, overriding user typos. However, `ba.validate()` must be run on custom `ParsedAddress` objects to flag deliberate state/pincode mismatches.
4. **IndicBERT Schema Pluralization:**
   * Note that IndicBERT uses `landmarks` (plural) whereas `bharataddress` uses `landmark` (singular).
   * IndicBERT groups house numbers, flat numbers, and prefix labels into `house_details`.
5. **IndicBERT Positional Bias on Stacked Landmark Prefixes:**
   * If an address starts with multiple stacked landmark clauses (e.g., `Opposite to City Centre Mall, Behind Chai Point...`) without a preceding house/building number, IndicBERT's token classification tends to tag the leading tokens as `O`. `bharataddress`'s deterministic cue segmenter excels in this specific scenario.

---

## 6. Conclusion & Stage 2 Readiness

Stage 1 validation confirms:
- **`bharataddress`** operates at **`0.18 ms`** latency with high precision on postal structure, India Post validation, DIGIPIN encoding, and phonetic normalization.
- **`IndicBERT`** operates at **`42.4 ms`** latency on CPU with superior token-level resolution for complex house details, floors, building names, and informal roads.
- The two libraries possess complementary strengths that directly inform the multi-agent architecture in Stage 2.
