#!/usr/bin/env python3
"""
scripts/validate_bharataddress.py
=================================
Comprehensive foundation validation script for the `bharataddress` library.
Exercises every documented module and function in isolation with real-world
Indian addresses and benchmarks parsing latency.

Status: Stage 1 — Foundation Validation
"""

import math
import sys
import time
from typing import Any

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


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two lat/lng coordinates."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def main():
    print("=" * 70)
    print(" PATA STAGE 1: BHARATADDRESS FOUNDATION VALIDATION")
    print("=" * 70)

    # 1. Package Installation & Version Check
    try:
        import bharataddress as ba
        version = getattr(ba, "__version__", "unknown")
        log_check("Library Import", True, f"bharataddress version={version}")
    except ImportError as e:
        log_check("Library Import", False, f"Failed to import bharataddress: {e}")
        print("\nSummary: 0/1 checks passed. Aborting validation.")
        sys.exit(1)

    # 2. Optional Extras Validation (indic + fuzzy)
    # Check indic transliteration
    try:
        import indic_transliteration
        log_check("Optional Extra: [indic]", True, f"indic_transliteration installed ({getattr(indic_transliteration, '__version__', 'present')})")
    except ImportError:
        log_check("Optional Extra: [indic]", False, "indic_transliteration not installed")

    # Check fuzzy (RapidFuzz)
    try:
        import rapidfuzz
        log_check("Optional Extra: [fuzzy]", True, f"RapidFuzz installed ({getattr(rapidfuzz, '__version__', 'present')})")
    except ImportError:
        log_check("Optional Extra: [fuzzy]", False, "RapidFuzz not installed")

    # Check graceful fallback in phonetic when RapidFuzz is absent
    try:
        from bharataddress import phonetic
        orig_rf = phonetic._HAS_RAPIDFUZZ
        # Simulate absence of RapidFuzz
        phonetic._HAS_RAPIDFUZZ = False
        fallback_score = phonetic.fuzzy_ratio("Gurgaon", "Gurugram")
        # Restore original state
        phonetic._HAS_RAPIDFUZZ = orig_rf
        log_check("Phonetic Fallback to difflib", fallback_score == 1.0, f"Fallback score={fallback_score}")
    except Exception as e:
        log_check("Phonetic Fallback to difflib", False, f"Error: {e}")

    # 3. Pincode Lookup Module
    print("\n--- Testing pincode module ---")
    try:
        # Known Bangalore pincode
        rec_560001 = ba.pincode.lookup("560001")
        valid_rec = (
            rec_560001 is not None
            and rec_560001.get("state") == "Karnataka"
            and rec_560001.get("city") == "Bangalore"
            and "latitude" in rec_560001
        )
        log_check(
            "pincode.lookup() known (560001)",
            valid_rec,
            f"State={rec_560001.get('state')}, City={rec_560001.get('city')}, Lat={rec_560001.get('latitude')}, Lng={rec_560001.get('longitude')}",
        )

        # Known Delhi pincode
        rec_110001 = ba.pincode.lookup("110001")
        valid_rec_del = (
            rec_110001 is not None
            and rec_110001.get("state") == "Delhi"
            and rec_110001.get("city") == "New Delhi"
        )
        log_check(
            "pincode.lookup() known (110001)",
            valid_rec_del,
            f"State={rec_110001.get('state')}, City={rec_110001.get('city')}",
        )

        # Invalid pincode lookup
        rec_invalid = ba.pincode.lookup("999999")
        log_check(
            "pincode.lookup() unknown (999999)",
            rec_invalid is None,
            f"Returned {rec_invalid} (expected None)",
        )
    except Exception as e:
        log_check("pincode.lookup()", False, f"Exception: {e}")

    # 4. DIGIPIN Encoding / Decoding Module
    print("\n--- Testing digipin module ---")
    try:
        test_lat, test_lng = 12.9716, 77.5946
        digipin_code = ba.digipin.encode(test_lat, test_lng)
        valid_encode = bool(digipin_code and len(digipin_code) == 12 and digipin_code.count("-") == 2)
        log_check("digipin.encode()", valid_encode, f"Lat/Lng ({test_lat}, {test_lng}) -> {digipin_code}")

        if digipin_code:
            dec_lat, dec_lng = ba.digipin.decode(digipin_code)
            dist_m = haversine_distance_meters(test_lat, test_lng, dec_lat, dec_lng)
            # DIGIPIN has ~4x4m grid resolution; round-trip error must be < 5 meters
            valid_decode = dist_m < 5.0
            log_check(
                "digipin.decode() Round-trip Precision",
                valid_decode,
                f"Decoded=({dec_lat:.6f}, {dec_lng:.6f}), Haversine error={dist_m:.3f}m (< 5.0m threshold)",
            )
    except Exception as e:
        log_check("digipin module", False, f"Exception: {e}")

    # 5. Core Address Parsing: parse() across diverse address archetypes
    print("\n--- Testing parse() on 6 benchmark address archetypes ---")
    test_cases = [
        {
            "id": "ADDR-1",
            "type": "Clean pincode + locality + building + landmark",
            "raw": "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru, Karnataka 560076",
            "expected_pincode": "560076",
            "expected_city": "Bangalore",
            "expected_state": "Karnataka",
            "min_confidence": 0.8,
        },
        {
            "id": "ADDR-2",
            "type": "Landmark-only / landmark-heavy without pincode",
            "raw": "Opposite to City Centre Mall, Behind Chai Point, Near Metro Pillar 124, MG Road, Bengaluru",
            "expected_pincode": None,
            "expected_city": "Bengaluru",
            "min_confidence": 0.3,
        },
        {
            "id": "ADDR-3",
            "type": "H.No. / S-O format with complex house numbering",
            "raw": "H.No. 4-12/A, S/O Rama Rao, Near Water Tank, Madhapur, Hyderabad, Telangana 500081",
            "expected_pincode": "500081",
            "expected_city": "Hyderabad",
            "expected_state": "Telangana",
            "min_confidence": 0.8,
        },
        {
            "id": "ADDR-4",
            "type": "Missing pincode with floor & building details",
            "raw": "2nd Floor, Krishna Niwas, Near Old Post Office, Shivaji Nagar, Pune, Maharashtra",
            "expected_pincode": None,
            "min_confidence": 0.3,
        },
        {
            "id": "ADDR-5",
            "type": "Mixed Hindi (Devanagari) + English script",
            "raw": "मकान नं १२, शांति कुंज, near railway station, Jaipur, Rajasthan 302001",
            "expected_pincode": "302001",
            "expected_city": "Jaipur",
            "expected_state": "Rajasthan",
            "min_confidence": 0.8,
            "transliterate": True,
        },
        {
            "id": "ADDR-6",
            "type": "Colloquial landmark phrasing with informal cues",
            "raw": "Opposite to red water tank behind chai ki tapri near pipal tree, gali no 4, Sangam Vihar, New Delhi 110080",
            "expected_pincode": "110080",
            "expected_state": "Delhi",
            "min_confidence": 0.8,
        },
    ]

    parsed_results: list[Any] = []
    for tc in test_cases:
        try:
            translit = tc.get("transliterate", False)
            res = ba.parse(tc["raw"], transliterate=translit)
            parsed_results.append(res)

            checks_passed = True
            details_list = []

            if "expected_pincode" in tc:
                pin_ok = res.pincode == tc["expected_pincode"]
                checks_passed = checks_passed and pin_ok
                details_list.append(f"pincode='{res.pincode}' (exp '{tc['expected_pincode']}')")

            if "expected_city" in tc:
                city_ok = res.city and (res.city.lower() == tc["expected_city"].lower())
                checks_passed = checks_passed and bool(city_ok)
                details_list.append(f"city='{res.city}' (exp '{tc['expected_city']}')")

            if "expected_state" in tc:
                state_ok = res.state and (res.state.lower() == tc["expected_state"].lower())
                checks_passed = checks_passed and bool(state_ok)
                details_list.append(f"state='{res.state}' (exp '{tc['expected_state']}')")

            conf_ok = res.confidence >= tc["min_confidence"]
            checks_passed = checks_passed and conf_ok
            details_list.append(f"conf={res.confidence:.2f}")

            log_check(f"parse() {tc['id']} ({tc['type']})", checks_passed, ", ".join(details_list))
        except Exception as e:
            log_check(f"parse() {tc['id']}", False, f"Exception: {e}")

    # 6. Formatting Module: format()
    print("\n--- Testing format() module ---")
    try:
        sample_parsed = parsed_results[0]
        f_post = ba.format(sample_parsed, style="india_post")
        f_single = ba.format(sample_parsed, style="single_line")
        f_label = ba.format(sample_parsed, style="label")

        ok_post = bool(f_post and "560076" in f_post and "\n" in f_post)
        ok_single = bool(f_single and "560076" in f_single and "\n" not in f_single)
        ok_label = bool(f_label and "Pincode: 560076" in f_label)

        log_check("format(style='india_post')", ok_post, f"{len(f_post.splitlines())} lines formatted")
        log_check("format(style='single_line')", ok_single, f"'{f_single[:60]}...'")
        log_check("format(style='label')", ok_label, f"Contains field prefixes: {f_label.splitlines()[0]}")
    except Exception as e:
        log_check("format() module", False, f"Exception: {e}")

    # 7. Validation & Deliverability Module
    print("\n--- Testing validate() & is_deliverable() ---")
    try:
        # Deliverable valid address
        valid_addr = parsed_results[0]
        v_res = ba.validate(valid_addr)
        deliv = ba.is_deliverable(valid_addr)
        log_check(
            "validate() on Deliverable Address",
            v_res["is_deliverable"] is True and len(v_res["issues"]) == 0,
            f"is_deliverable={deliv}, overall_score={v_res['overall']}, issues={v_res['issues']}",
        )

        # Deliberately broken address: Mismatched state/pincode
        # Pincode 560076 is in Karnataka, but state set to Maharashtra
        broken_mismatch = ba.ParsedAddress(
            raw="Test Mismatch",
            cleaned="Test Mismatch",
            pincode="560076",
            city="Bangalore",
            state="Maharashtra",
        )
        v_mismatch = ba.validate(broken_mismatch)
        has_state_issue = any("state mismatch" in iss for iss in v_mismatch["issues"])
        log_check(
            "validate() State/Pincode Mismatch Detection",
            has_state_issue,
            f"Detected issues: {v_mismatch['issues']}",
        )

        # Broken address: Unknown pincode
        broken_bad_pin = ba.ParsedAddress(
            raw="Test Bad Pin",
            cleaned="Test Bad Pin",
            pincode="999999",
            city="Nowhere",
            state="Unknown",
        )
        v_bad_pin = ba.validate(broken_bad_pin)
        has_pin_issue = any("not in India Post directory" in iss for iss in v_bad_pin["issues"])
        log_check(
            "validate() Unknown Pincode Detection",
            has_pin_issue,
            f"Detected issues: {v_bad_pin['issues']}",
        )

        # Incomplete address missing city/state/pincode
        incomplete_addr = ba.ParsedAddress(
            raw="Only Landmark",
            cleaned="Only Landmark",
            landmark="Apollo Hospital",
        )
        log_check(
            "is_deliverable() on Incomplete Address",
            ba.is_deliverable(incomplete_addr) is False,
            f"is_deliverable={ba.is_deliverable(incomplete_addr)} (expected False)",
        )
    except Exception as e:
        log_check("validate() / is_deliverable()", False, f"Exception: {e}")

    # 8. Phonetic Module
    print("\n--- Testing phonetic module ---")
    try:
        # Alias normalization
        norm_ggn = ba.phonetic.normalise("Gurgaon")
        norm_ggm = ba.phonetic.normalise("Gurugram")
        norm_blr = ba.phonetic.normalise("Bangalore")
        norm_bgl = ba.phonetic.normalise("Bengaluru")
        norm_cal = ba.phonetic.normalise("Calcutta")
        norm_kol = ba.phonetic.normalise("Kolkata")

        log_check(
            "phonetic.normalise() Gurgaon/Gurugram",
            norm_ggn == norm_ggm == "gurgaon",
            f"Gurgaon='{norm_ggn}', Gurugram='{norm_ggm}'",
        )
        log_check(
            "phonetic.normalise() Bangalore/Bengaluru",
            norm_blr == norm_bgl == "bangalore",
            f"Bangalore='{norm_blr}', Bengaluru='{norm_bgl}'",
        )
        log_check(
            "phonetic.normalise() Calcutta/Kolkata",
            norm_cal == norm_kol == "calcutta",
            f"Calcutta='{norm_cal}', Kolkata='{norm_kol}'",
        )

        # Fuzzy ratio
        ratio_ggn = ba.phonetic.fuzzy_ratio("Gurgaon", "Gurugram")
        ratio_blr = ba.phonetic.fuzzy_ratio("Bengaluru", "Bangalore")
        log_check("phonetic.fuzzy_ratio() Gurgaon vs Gurugram", ratio_ggn == 1.0, f"ratio={ratio_ggn}")
        log_check("phonetic.fuzzy_ratio() Bengaluru vs Bangalore", ratio_blr == 1.0, f"ratio={ratio_blr}")

        # Best match
        b_match = ba.phonetic.best_match("Bangalore", ["Bengaluru", "Mumbai", "Delhi"])
        log_check(
            "phonetic.best_match()",
            b_match is not None and b_match[0] == "Bengaluru" and b_match[1] == 1.0,
            f"Result={b_match}",
        )
    except Exception as e:
        log_check("phonetic module", False, f"Exception: {e}")

    # 9. Geocoder Module (Offline Centroid Mode)
    print("\n--- Testing geocode module ---")
    try:
        # Known pincode with centroid coverage in embedded directory
        p_centroid = ba.parse("560001 Bangalore")
        geo_hit = ba.geocode(p_centroid, online=False)
        log_check(
            "geocode() Offline Pincode Centroid (560001)",
            geo_hit is not None and isinstance(geo_hit, tuple) and len(geo_hit) == 2,
            f"Coordinates={geo_hit}",
        )

        # Address without pincode / without centroid (should return None safely)
        p_nocentroid = ba.parse("Random Unknown Place Without Pincode")
        geo_miss = ba.geocode(p_nocentroid, online=False)
        log_check(
            "geocode() Offline Miss Handling",
            geo_miss is None,
            f"Returned {geo_miss} without crashing",
        )
    except Exception as e:
        log_check("geocoder module", False, f"Exception: {e}")

    # 10. Similarity Module: address_similarity()
    print("\n--- Testing address_similarity module ---")
    try:
        sim_short = ba.address_similarity("MG Road, Bangalore", "Mahatma Gandhi Road, Bengaluru")
        sim_full = ba.address_similarity(
            "Flat 402, Shanti Heights, MG Road, Bangalore 560001, Karnataka",
            "Flat 402, Shanti Heights, Mahatma Gandhi Road, Bengaluru 560001, Karnataka",
        )
        log_check(
            "address_similarity() Street + City Aliasing",
            sim_short >= 0.40,
            f"Score={sim_short:.2f} (Street alias + City canonical match)",
        )
        log_check(
            "address_similarity() Full Identical Structure",
            sim_full == 1.0,
            f"Score={sim_full:.2f}",
        )
    except Exception as e:
        log_check("address_similarity module", False, f"Exception: {e}")

    # 11. Batch Parsing: parse_batch()
    print("\n--- Testing parse_batch module ---")
    try:
        batch_inputs = [
            "560001 Bangalore",
            "110001 New Delhi",
            "400001 Mumbai",
            "600001 Chennai",
        ]
        batch_out = ba.parse_batch(batch_inputs)
        log_check(
            "parse_batch() Count & Integrity",
            len(batch_out) == len(batch_inputs) and all(isinstance(p, ba.ParsedAddress) for p in batch_out),
            f"Processed {len(batch_out)}/{len(batch_inputs)} records",
        )
    except Exception as e:
        log_check("parse_batch module", False, f"Exception: {e}")

    # 12. Latency Benchmark: 50 calls to parse()
    print("\n--- Running parse() Latency Benchmark (50 iterations) ---")
    try:
        benchmark_addr = (
            "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru, Karnataka 560076"
        )
        # Warmup call
        ba.parse(benchmark_addr)

        times_ms: list[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            ba.parse(benchmark_addr)
            t1 = time.perf_counter()
            times_ms.append((t1 - t0) * 1000.0)

        min_t = min(times_ms)
        max_t = max(times_ms)
        mean_t = sum(times_ms) / len(times_ms)
        sorted_t = sorted(times_ms)
        median_t = sorted_t[len(sorted_t) // 2]
        p95_t = sorted_t[int(len(sorted_t) * 0.95)]

        print(f"  Iterations: {len(times_ms)}")
        print(f"  Mean:       {mean_t:.3f} ms")
        print(f"  Median:     {median_t:.3f} ms")
        print(f"  Min:        {min_t:.3f} ms")
        print(f"  Max:        {max_t:.3f} ms")
        print(f"  P95:        {p95_t:.3f} ms")

        # README claims ~5ms; we check that it is sub-15ms on this CPU
        log_check("parse() Latency Target (<15ms)", mean_t < 15.0, f"Mean latency={mean_t:.3f}ms")
    except Exception as e:
        log_check("parse() latency benchmark", False, f"Exception: {e}")

    # Final Summary
    print("\n" + "=" * 70)
    print(f"FINAL SUMMARY: {passed_checks}/{total_checks} checks passed")
    print("=" * 70)

    if failed_checks > 0:
        print(f"CRITICAL: {failed_checks} check(s) failed!")
        sys.exit(1)
    else:
        print("All bharataddress foundation validation checks PASSED successfully.")


if __name__ == "__main__":
    main()
