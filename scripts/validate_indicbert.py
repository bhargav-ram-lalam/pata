#!/usr/bin/env python3
"""
scripts/validate_indicbert.py
=============================
Comprehensive foundation validation script for the IndicBERT address NER model:
`shiprocket-ai/open-indicbert-indian-address-ner`.

Validates model loading, schema/id2label discovery, entity extraction across
standard test addresses, landmark resilience on informal phrasing, and latency.

Status: Stage 1 — Foundation Validation
"""

import sys
import time
from typing import Any, Dict, List

# Ensure stdout uses UTF-8 encoding across all platforms
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ---------------------------------------------------------------------------
# Test Runner & Tracking
# ---------------------------------------------------------------------------
total_checks = 0
passed_checks = 0
failed_checks = 0


def log_check(name: str, passed: bool, details: str = ""):
    global total_checks, passed_checks, failed_checks
    total_checks += 1
    if passed:
        passed_checks += 1
        status = "[PASS]"
    else:
        failed_checks += 1
        status = "[FAIL]"
    msg = f"{status} {name}"
    if details:
        msg += f" -> {details}"
    print(msg)


def main():
    print("=" * 70)
    print(" PATA STAGE 1: INDICBERT NER MODEL VALIDATION")
    print("=" * 70)

    # 1. Environment & Package Check
    try:
        import torch
        import transformers

        torch_ver = getattr(torch, "__version__", "unknown")
        trans_ver = getattr(transformers, "__version__", "unknown")
        cuda_avail = torch.cuda.is_available()
        device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU"

        log_check(
            "Library & Environment Check",
            True,
            f"PyTorch={torch_ver}, Transformers={trans_ver}, Device={device_name} (CUDA={cuda_avail})",
        )
    except ImportError as e:
        log_check("Library & Environment Check", False, f"ImportError: {e}")
        print("\nSummary: 0/1 checks passed. Aborting validation.")
        sys.exit(1)

    model_name = "shiprocket-ai/open-indicbert-indian-address-ner"
    print(f"\nTarget Model: {model_name}")

    # 2. Cold Start Load Time & Architecture Inspection
    from transformers import (
        AutoConfig,
        AutoModelForTokenClassification,
        AutoTokenizer,
        pipeline,
    )

    t0_load = time.perf_counter()
    try:
        config = AutoConfig.from_pretrained(model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        t1_load = time.perf_counter()
        load_time_sec = t1_load - t0_load

        total_params = sum(p.numel() for p in model.parameters())
        model_size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024 * 1024)

        log_check(
            "Model Cold Load",
            True,
            f"Loaded in {load_time_sec:.2f}s | Params: {total_params:,} (~{model_size_mb:.1f} MB)",
        )
    except Exception as e:
        log_check("Model Cold Load", False, f"Failed to load model: {e}")
        print("\nAborting further tests due to model load failure.")
        sys.exit(1)

    # 3. Label List & Schema Inspection (id2label)
    print("\n--- Inspecting Model Label Schema (id2label) ---")
    id2label: Dict[int, str] = config.id2label
    print("Discovered id2label mapping:")
    for idx in sorted(id2label.keys()):
        print(f"  {idx:2d}: {id2label[idx]}")

    expected_entity_types = {
        "building_name",
        "city",
        "country",
        "floor",
        "house_details",
        "locality",
        "pincode",
        "road",
        "state",
        "sub_locality",
        "landmarks",
    }
    extracted_types = {
        lbl.replace("B-", "").replace("I-", "")
        for lbl in id2label.values()
        if lbl != "O"
    }

    log_check(
        "id2label Schema Integrity",
        expected_entity_types.issubset(extracted_types),
        f"Discovered {len(extracted_types)} entity types: {sorted(extracted_types)}",
    )

    # 4. Pipeline Setup
    try:
        ner_pipe = pipeline(
            "token-classification",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
        )
        log_check("Inference Pipeline Creation", True, "pipeline(aggregation_strategy='simple') initialized")
    except Exception as e:
        log_check("Inference Pipeline Creation", False, f"Failed: {e}")
        sys.exit(1)

    # 5. Inference on 6 Benchmark Test Addresses
    print("\n--- Running Inference on 6 Benchmark Test Addresses ---")
    test_cases = [
        {
            "id": "ADDR-1",
            "type": "Clean pincode + locality + building + landmark",
            "raw": "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru, Karnataka 560076",
            "expected_entities": ["house_details", "building_name", "landmarks", "city", "state", "pincode"],
        },
        {
            "id": "ADDR-2",
            "type": "Landmark-only / landmark-heavy without pincode",
            "raw": "Opposite to City Centre Mall, Behind Chai Point, Near Metro Pillar 124, MG Road, Bengaluru",
            "expected_entities": ["road", "city"],
        },
        {
            "id": "ADDR-3",
            "type": "H.No. / S-O format with complex house numbering",
            "raw": "H.No. 4-12/A, S/O Rama Rao, Near Water Tank, Madhapur, Hyderabad, Telangana 500081",
            "expected_entities": ["house_details", "landmarks", "locality", "city", "state", "pincode"],
        },
        {
            "id": "ADDR-4",
            "type": "Missing pincode with floor & building details",
            "raw": "2nd Floor, Krishna Niwas, Near Old Post Office, Shivaji Nagar, Pune, Maharashtra",
            "expected_entities": ["floor", "building_name", "landmarks", "locality", "city", "state"],
        },
        {
            "id": "ADDR-5",
            "type": "Mixed Hindi (Devanagari) + English script",
            "raw": "मकान नं १२, शांति कुंज, near railway station, Jaipur, Rajasthan 302001",
            "expected_entities": ["landmarks", "city", "state", "pincode"],
        },
        {
            "id": "ADDR-6",
            "type": "Colloquial landmark phrasing with informal cues",
            "raw": "Opposite to red water tank behind chai ki tapri near pipal tree, gali no 4, Sangam Vihar, New Delhi 110080",
            "expected_entities": ["locality", "city", "pincode"],
        },
    ]

    all_inferences: List[Dict[str, Any]] = []
    for tc in test_cases:
        print(f"\n[{tc['id']}] ({tc['type']})")
        print(f"  Raw: \"{tc['raw']}\"")
        t0_inf = time.perf_counter()
        entities = ner_pipe(tc["raw"])
        t1_inf = time.perf_counter()
        latency_ms = (t1_inf - t0_inf) * 1000.0

        found_groups = set()
        print("  Extracted Entities:")
        for ent in entities:
            grp = ent["entity_group"]
            text = ent["word"].strip()
            score = float(ent["score"])
            found_groups.add(grp)
            print(f"    - {grp:15s}: \"{text}\" (conf: {score:.3f}, [{ent['start']}:{ent['end']}])")

        all_inferences.append({
            "id": tc["id"],
            "raw": tc["raw"],
            "entities": entities,
            "latency_ms": latency_ms,
            "groups": found_groups,
        })

        # Verify key entities were captured
        missing = [req for req in tc["expected_entities"] if req not in found_groups]
        passed = (len(entities) > 0) and (len(missing) == 0)
        details = f"Latency={latency_ms:.1f}ms, Found={sorted(found_groups)}"
        if missing:
            details += f", Missing expected={missing}"
        log_check(f"Inference & Entity Extraction {tc['id']}", passed, details)

    # 6. Explicit Landmark Phrasing Stress Test
    # Testing descriptive landmark cues where rule-based parsers struggle
    print("\n--- Stress Testing Landmark Cue Robustness ---")
    stress_landmark_addr = (
        "Behind old banyan tree next to Sharma tea stall, 3rd cross, Indiranagar, Bangalore"
    )
    print(f"Input: \"{stress_landmark_addr}\"")
    t0_stress = time.perf_counter()
    stress_ents = ner_pipe(stress_landmark_addr)
    t1_stress = time.perf_counter()
    stress_landmarks = [
        ent["word"].strip()
        for ent in stress_ents
        if ent["entity_group"] == "landmarks"
    ]
    print(f"Extracted Entities:")
    for ent in stress_ents:
        print(f"  - {ent['entity_group']:15s}: \"{ent['word'].strip()}\" (conf: {float(ent['score']):.3f})")
    log_check(
        "Descriptive Landmark Span Extraction",
        len(stress_landmarks) > 0,
        f"Captured landmark spans: {stress_landmarks} (latency={(t1_stress - t0_stress)*1000:.1f}ms)",
    )

    # 7. Latency Benchmarking (10 runs on benchmark address)
    print("\n--- Running Inference Latency Benchmark (10 iterations) ---")
    benchmark_addr = test_cases[0]["raw"]
    latencies: List[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        ner_pipe(benchmark_addr)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    mean_lat = sum(latencies) / len(latencies)
    median_lat = sorted(latencies)[len(latencies) // 2]
    min_lat = min(latencies)
    max_lat = max(latencies)

    print(f"  Iterations: {len(latencies)}")
    print(f"  Mean:       {mean_lat:.2f} ms")
    print(f"  Median:     {median_lat:.2f} ms")
    print(f"  Min:        {min_lat:.2f} ms")
    print(f"  Max:        {max_lat:.2f} ms")
    log_check("Inference Latency Benchmark (<200ms)", mean_lat < 200.0, f"Mean latency={mean_lat:.2f}ms on {device_name}")

    # Final Summary
    print("\n" + "=" * 70)
    print(f"FINAL SUMMARY: {passed_checks}/{total_checks} checks passed")
    print("=" * 70)

    if failed_checks > 0:
        print(f"CRITICAL: {failed_checks} check(s) failed!")
        sys.exit(1)
    else:
        print("All IndicBERT NER foundation validation checks PASSED successfully.")


if __name__ == "__main__":
    main()
