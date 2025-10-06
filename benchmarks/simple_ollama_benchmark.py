#!/usr/bin/env python3
"""
Simple Ollama Performance Benchmark

Measures actual performance of Ollama node:
- Latency (avg, p50, p95, p99)
- Success rate
- Throughput (requests/sec)
"""

import asyncio
import json
import time
import statistics
from typing import List
from dataclasses import dataclass, asdict
import httpx


@dataclass
class RequestResult:
    success: bool
    latency_ms: float
    timestamp: float
    error: str = ""


async def send_request(client: httpx.AsyncClient, url: str, payload: dict) -> RequestResult:
    """Send a single request and measure latency."""
    start = time.time()
    try:
        response = await client.post(url, json=payload, timeout=30.0)
        latency = (time.time() - start) * 1000

        return RequestResult(
            success=response.status_code == 200,
            latency_ms=latency,
            timestamp=start
        )
    except Exception as e:
        latency = (time.time() - start) * 1000
        return RequestResult(
            success=False,
            latency_ms=latency,
            timestamp=start,
            error=str(e)
        )


async def run_benchmark(
    base_url: str = "http://localhost:11434",
    num_requests: int = 50,
    concurrency: int = 5,
    model: str = "llama3.2"
):
    """Run benchmark against Ollama node."""

    print(f"🔬 Running Ollama Performance Benchmark")
    print(f"   URL: {base_url}")
    print(f"   Model: {model}")
    print(f"   Requests: {num_requests}")
    print(f"   Concurrency: {concurrency}")
    print()

    payloads = [
        {"model": model, "messages": [{"role": "user", "content": "Hello!"}], "stream": False},
        {"model": model, "messages": [{"role": "user", "content": "What is 2+2?"}], "stream": False},
        {"model": model, "messages": [{"role": "user", "content": "Explain AI in one sentence."}], "stream": False},
    ]

    results: List[RequestResult] = []
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(num_requests):
            payload = payloads[i % len(payloads)]
            task = send_request(client, f"{base_url}/api/chat", payload)
            tasks.append(task)

            # Control concurrency
            if len(tasks) >= concurrency:
                batch_results = await asyncio.gather(*tasks)
                results.extend(batch_results)
                tasks = []
                print(f"  Completed {len(results)}/{num_requests} requests...")

        # Process remaining
        if tasks:
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

    duration = time.time() - start_time

    # Analyze results
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if not successful:
        print("\n❌ All requests failed!")
        return None

    latencies = [r.latency_ms for r in successful]
    latencies_sorted = sorted(latencies)

    metrics = {
        "benchmark_config": {
            "base_url": base_url,
            "model": model,
            "num_requests": num_requests,
            "concurrency": concurrency,
            "duration_seconds": round(duration, 2)
        },
        "results": {
            "total_requests": len(results),
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "success_rate": round(len(successful) / len(results), 4),
            "requests_per_second": round(len(results) / duration, 2),
        },
        "latency_ms": {
            "min": round(min(latencies), 1),
            "max": round(max(latencies), 1),
            "avg": round(statistics.mean(latencies), 1),
            "median": round(statistics.median(latencies), 1),
            "p50": round(latencies_sorted[int(len(latencies_sorted) * 0.50)], 1),
            "p95": round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 1),
            "p99": round(latencies_sorted[min(int(len(latencies_sorted) * 0.99), len(latencies_sorted) - 1)], 1),
        },
        "timestamp": int(time.time()),
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Print results
    print(f"\n{'='*70}")
    print(f"📊 BENCHMARK RESULTS")
    print(f"{'='*70}")
    print(f"\n✅ Success Rate: {metrics['results']['success_rate']*100:.1f}%")
    print(f"   Total requests: {metrics['results']['total_requests']}")
    print(f"   Successful: {metrics['results']['successful_requests']}")
    print(f"   Failed: {metrics['results']['failed_requests']}")

    print(f"\n⚡ Throughput: {metrics['results']['requests_per_second']:.2f} req/s")
    print(f"   Duration: {metrics['benchmark_config']['duration_seconds']:.2f}s")

    print(f"\n📈 Latency (milliseconds):")
    print(f"   Min:    {metrics['latency_ms']['min']:>8.1f} ms")
    print(f"   Avg:    {metrics['latency_ms']['avg']:>8.1f} ms")
    print(f"   Median: {metrics['latency_ms']['median']:>8.1f} ms")
    print(f"   P95:    {metrics['latency_ms']['p95']:>8.1f} ms")
    print(f"   P99:    {metrics['latency_ms']['p99']:>8.1f} ms")
    print(f"   Max:    {metrics['latency_ms']['max']:>8.1f} ms")
    print(f"\n{'='*70}\n")

    # Save results
    output_file = f"benchmarks/results/ollama_benchmark_{model}_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"💾 Results saved to: {output_file}")

    return metrics


if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "llama3.2"
    num_requests = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    asyncio.run(run_benchmark(model=model, num_requests=num_requests))
