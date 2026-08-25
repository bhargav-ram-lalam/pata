"""
tests/load_test.py
==================
Asynchronous load testing tool for evaluating Pata throughput and percentile latencies.
Generates empirical scalability and SLA benchmarks for HIGH vs MEDIUM tier traffic.

Usage:
  python tests/load_test.py --concurrency 10 --requests 50
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import statistics
import sys
import time
from typing import List, Dict, Any

# Ensure workspace root is in sys.path when running standalone
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

BENCHMARK_ADDRESSES = [
    # HIGH Tier (Structured)
    "Flat 402, Shanti Heights, Near Apollo Hospital, Bannerghatta Road, Bengaluru 560076",
    "B-204, DLF Phase 5, Golf Course Road, Gurugram, Haryana 122009",
    "Plot 12, Sector 21, Gurugram, Haryana 122016",
    # MEDIUM / LOW Tier (Messy / Colloquial / Missing Pin)
    "Opp SBI Bank, Near Jain Mandir, Andheri East, Mumbai 400069",
    "Samne Gurudwara, Gali No. 3, Laxmi Nagar, Delhi",
    "Village Bhondsi, Tehsil Sohna, Dist. Gurgaon, Haryana",
]


async def run_http_load_test(
    base_url: str,
    api_key: str,
    total_requests: int,
    concurrency: int,
) -> Dict[str, Any]:
    """Execute load test over HTTP against running API instance."""
    semaphore = asyncio.Semaphore(concurrency)
    latencies: List[float] = []
    tier_latencies: Dict[str, List[float]] = {"high": [], "medium": [], "low": []}
    successes = 0
    failures = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def _worker(idx: int):
            nonlocal successes, failures
            addr = BENCHMARK_ADDRESSES[idx % len(BENCHMARK_ADDRESSES)]
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    resp = await client.post(
                        f"{base_url}/v1/resolve",
                        json={"address": addr},
                        headers={"X-API-Key": api_key},
                    )
                    lat_ms = (time.perf_counter() - t0) * 1000.0
                    latencies.append(lat_ms)

                    if resp.status_code == 200:
                        successes += 1
                        data = resp.json()
                        tier = data.get("evidence", {}).get("agent4_tier", "low").lower()
                        tier_latencies.get(tier, tier_latencies["low"]).append(lat_ms)
                    else:
                        failures += 1
                except Exception:
                    failures += 1

        t_start = time.perf_counter()
        tasks = [_worker(i) for i in range(total_requests)]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - t_start

    return _compute_stats(latencies, tier_latencies, successes, failures, total_time)


async def run_in_process_load_test(
    total_requests: int,
    concurrency: int,
) -> Dict[str, Any]:
    """Execute load test in-process via thread pool."""
    from pipeline import resolve_address, preload_models

    # Warm up models before benchmark
    preload_models()

    semaphore = asyncio.Semaphore(concurrency)
    latencies: List[float] = []
    tier_latencies: Dict[str, List[float]] = {"high": [], "medium": [], "low": []}
    successes = 0
    failures = 0

    loop = asyncio.get_running_loop()

    async def _worker(idx: int):
        nonlocal successes, failures
        addr = BENCHMARK_ADDRESSES[idx % len(BENCHMARK_ADDRESSES)]
        async with semaphore:
            t0 = time.perf_counter()
            try:
                res = await loop.run_in_executor(None, lambda: resolve_address(addr, skip_osm=True))
                lat_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(lat_ms)
                successes += 1
                tier = res.evidence.get("agent4_tier", "low").lower()
                tier_latencies.get(tier, tier_latencies["low"]).append(lat_ms)
            except Exception:
                failures += 1

    t_start = time.perf_counter()
    tasks = [_worker(i) for i in range(total_requests)]
    await asyncio.gather(*tasks)
    total_time = time.perf_counter() - t_start

    return _compute_stats(latencies, tier_latencies, successes, failures, total_time)


def _compute_stats(
    latencies: List[float],
    tier_latencies: Dict[str, List[float]],
    successes: int,
    failures: int,
    total_time: float,
) -> Dict[str, Any]:
    if not latencies:
        return {"error": "No requests recorded"}

    sorted_lat = sorted(latencies)
    p50 = sorted_lat[int(len(sorted_lat) * 0.50)]
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)]

    return {
        "total_requests": len(latencies),
        "successes": successes,
        "failures": failures,
        "total_time_sec": round(total_time, 2),
        "throughput_rps": round(len(latencies) / total_time, 2),
        "latency_mean_ms": round(statistics.mean(latencies), 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
        "tier_breakdown": {
            k: {
                "count": len(v),
                "mean_ms": round(statistics.mean(v), 2) if v else 0.0,
                "p95_ms": round(sorted(v)[int(len(v) * 0.95)], 2) if v else 0.0,
            }
            for k, v in tier_latencies.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Pata Load Testing Harness")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers (default: 10)")
    parser.add_argument("--requests", type=int, default=50, help="Total requests to dispatch (default: 50)")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Target API URL")
    parser.add_argument("--api-key", type=str, default="pata_dev_key", help="API key")
    parser.add_argument("--in-process", action="store_true", help="Run directly in-process without network")

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(f" PATA STAGE 3: CONCURRENT LOAD & LATENCY BENCHMARK")
    print(f" Requests: {args.requests} | Concurrency: {args.concurrency} | Mode: {'In-Process' if args.in_process else args.url}")
    print("=" * 70)

    if args.in_process or not HAS_HTTPX:
        stats = asyncio.run(run_in_process_load_test(args.requests, args.concurrency))
    else:
        try:
            stats = asyncio.run(run_http_load_test(args.url, args.api_key, args.requests, args.concurrency))
        except Exception as e:
            print(f"Could not connect to {args.url} ({e}). Falling back to in-process mode.")
            stats = asyncio.run(run_in_process_load_test(args.requests, args.concurrency))

    print(f"\nResults Summary:")
    print(f"  Total Requests:  {stats['total_requests']}")
    print(f"  Successful:      {stats['successes']}")
    print(f"  Failed:          {stats['failures']}")
    print(f"  Total Duration:  {stats['total_time_sec']}s")
    print(f"  Throughput:      {stats['throughput_rps']} req/sec")
    print()
    print(f"Latency Percentiles:")
    print(f"  Mean:            {stats['latency_mean_ms']} ms")
    print(f"  P50 (Median):    {stats['latency_p50_ms']} ms")
    print(f"  P95:             {stats['latency_p95_ms']} ms")
    print(f"  P99:             {stats['latency_p99_ms']} ms")
    print()
    print(f"Tier Breakdown:")
    for tier, data in stats["tier_breakdown"].items():
        print(f"  - {tier.upper():6s}: count={data['count']:2d}, mean={data['mean_ms']:6.2f}ms, p95={data['p95_ms']:6.2f}ms")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
