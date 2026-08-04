"""
Load test for the Content Moderation SaaS, hitting the full pipeline
through the gateway at increasing concurrency levels. Measures latency
and throughput to inform the report's Costs section.

Usage:
    python load_test.py

Requires the full stack running (docker compose up) and a registered
test user. Run 'docker stats' in a separate terminal during the test
to capture CPU/RAM consumption alongside these latency numbers.
"""
import asyncio
import statistics
import time

import httpx

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "loadtest@example.com"
TEST_PASSWORD = "loadtestpass123"

# Concurrency levels to test, one after another
CONCURRENCY_LEVELS = [1, 5, 10, 20, 50]
REQUESTS_PER_LEVEL = 100


async def ensure_test_user() -> str:
    """Registers the load-test user if needed, then logs in and
    returns a bearer token to use for all requests."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"{BASE_URL}/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        # Ignore the response here — a 409 (already registered) is
        # expected on repeat runs and is not an error for our purposes.

        login_response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        login_response.raise_for_status()
        return login_response.json()["access_token"]


async def send_one_request(client: httpx.AsyncClient, token: str) -> tuple[float, int]:
    """Sends a single submission request and returns (latency_seconds, status_code)."""
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/submissions",
            json={"text": "You are a disgusting waste of space and should shut up forever."},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        elapsed = time.perf_counter() - start
        return elapsed, response.status_code
    except httpx.HTTPError:
        elapsed = time.perf_counter() - start
        return elapsed, -1


async def run_at_concurrency(concurrency: int, total_requests: int, token: str) -> dict:
    """Fires `total_requests` requests, `concurrency` at a time, and
    returns summary statistics for this concurrency level."""
    latencies = []
    status_codes = []

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_request():
            async with semaphore:
                return await send_one_request(client, token)

        start_time = time.perf_counter()
        results = await asyncio.gather(*[bounded_request() for _ in range(total_requests)])
        total_time = time.perf_counter() - start_time

    for latency, status in results:
        latencies.append(latency)
        status_codes.append(status)

    success_count = sum(1 for s in status_codes if s == 201)
    error_count = total_requests - success_count

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "total_time_seconds": round(total_time, 3),
        "throughput_req_per_sec": round(total_requests / total_time, 2),
        "success_count": success_count,
        "error_count": error_count,
        "latency_mean_ms": round(statistics.mean(latencies) * 1000, 2),
        "latency_median_ms": round(statistics.median(latencies) * 1000, 2),
        "latency_p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 2),
        "latency_max_ms": round(max(latencies) * 1000, 2),
    }


async def main():
    print("Setting up test user...")
    token = await ensure_test_user()
    print("Ready. Starting load test.\n")
    print("TIP: run 'docker stats' in another terminal now to capture CPU/RAM usage during this run.\n")
    await asyncio.sleep(3)

    all_results = []

    for concurrency in CONCURRENCY_LEVELS:
        print(f"--- Testing at concurrency={concurrency} ({REQUESTS_PER_LEVEL} requests) ---")
        result = await run_at_concurrency(concurrency, REQUESTS_PER_LEVEL, token)
        all_results.append(result)

        print(f"  Throughput:     {result['throughput_req_per_sec']} req/sec")
        print(f"  Mean latency:   {result['latency_mean_ms']} ms")
        print(f"  Median latency: {result['latency_median_ms']} ms")
        print(f"  p95 latency:    {result['latency_p95_ms']} ms")
        print(f"  Max latency:    {result['latency_max_ms']} ms")
        print(f"  Success/Error:  {result['success_count']}/{result['error_count']}")
        print()

        await asyncio.sleep(2)  # brief pause between levels

    print("=== Summary table (copy into your report) ===\n")
    print(f"{'Concurrency':<12} {'Throughput (req/s)':<20} {'Mean (ms)':<12} {'p95 (ms)':<12} {'Errors':<8}")
    for r in all_results:
        print(
            f"{r['concurrency']:<12} {r['throughput_req_per_sec']:<20} "
            f"{r['latency_mean_ms']:<12} {r['latency_p95_ms']:<12} {r['error_count']:<8}"
        )


if __name__ == "__main__":
    asyncio.run(main())