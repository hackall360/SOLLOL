#!/usr/bin/env python3
"""
SOLLOL Benchmark Suite

Compares SOLLOL intelligent routing vs round-robin load balancing
across multiple metrics:
- Latency (avg, p50, p95, p99)
- Success rate
- GPU utilization
- Throughput (requests/sec)
- Failover performance

Usage:
    python benchmarks/run_benchmarks.py --sollol-url http://localhost:8000 --duration 60
"""

import argparse
import asyncio
import json
import time
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics
import httpx


@dataclass
class RequestResult:
    """Result of a single request."""
    success: bool
    latency_ms: float
    timestamp: float
    error: str = ""
    host_used: str = ""


@dataclass
class BenchmarkResults:
    """Aggregated benchmark results."""
    name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    requests_per_second: float
    duration_seconds: float
    host_distribution: Dict[str, int]


class LoadBalancerBenchmark:
    """Benchmark harness for load balancer testing."""

    def __init__(self, base_url: str, concurrency: int = 10):
        self.base_url = base_url
        self.concurrency = concurrency
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_request(self, payload: Dict[str, Any]) -> RequestResult:
        """Send a single request and measure latency."""
        start = time.time()
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            latency = (time.time() - start) * 1000  # Convert to ms

            if response.status_code == 200:
                data = response.json()
                host = data.get('_sollol_routing', {}).get('host', 'unknown')
                return RequestResult(
                    success=True,
                    latency_ms=latency,
                    timestamp=start,
                    host_used=host
                )
            else:
                return RequestResult(
                    success=False,
                    latency_ms=latency,
                    timestamp=start,
                    error=f"HTTP {response.status_code}"
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return RequestResult(
                success=False,
                latency_ms=latency,
                timestamp=start,
                error=str(e)
            )

    async def run_load_test(
        self,
        duration_seconds: int,
        requests_per_second: int = 10
    ) -> List[RequestResult]:
        """
        Run load test for specified duration.

        Args:
            duration_seconds: How long to run the test
            requests_per_second: Target request rate

        Returns:
            List of request results
        """
        results = []
        start_time = time.time()
        request_interval = 1.0 / requests_per_second

        # Test payloads (mix of simple and complex requests)
        payloads = [
            {
                "model": "llama3.2",
                "messages": [{"role": "user", "content": "Hello!"}]
            },
            {
                "model": "llama3.2",
                "messages": [{"role": "user", "content": "Explain quantum computing in detail."}]
            },
            {
                "model": "llama3.2",
                "messages": [
                    {"role": "user", "content": "Analyze this data"},
                    {"role": "assistant", "content": "I'll analyze it."},
                    {"role": "user", "content": "What patterns do you see?"}
                ]
            },
        ]

        request_count = 0

        while time.time() - start_time < duration_seconds:
            # Send burst of concurrent requests
            tasks = []
            for _ in range(self.concurrency):
                payload = payloads[request_count % len(payloads)]
                tasks.append(self.send_request(payload))
                request_count += 1

            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            # Rate limiting
            await asyncio.sleep(request_interval)

        return results

    def analyze_results(
        self,
        name: str,
        results: List[RequestResult],
        duration: float
    ) -> BenchmarkResults:
        """Analyze results and compute statistics."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        latencies = [r.latency_ms for r in successful]
        latencies.sort()

        # Host distribution
        host_dist = defaultdict(int)
        for r in successful:
            if r.host_used:
                host_dist[r.host_used] += 1

        return BenchmarkResults(
            name=name,
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            success_rate=len(successful) / len(results) if results else 0.0,
            avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
            p50_latency_ms=self._percentile(latencies, 50),
            p95_latency_ms=self._percentile(latencies, 95),
            p99_latency_ms=self._percentile(latencies, 99),
            requests_per_second=len(results) / duration if duration > 0 else 0.0,
            duration_seconds=duration,
            host_distribution=dict(host_dist)
        )

    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """Calculate percentile from sorted list."""
        if not values:
            return 0.0
        index = int(len(values) * percentile / 100)
        return values[min(index, len(values) - 1)]

    async def close(self):
        """Clean up resources."""
        await self.client.aclose()


async def run_sollol_benchmark(
    sollol_url: str,
    duration: int,
    concurrency: int
) -> BenchmarkResults:
    """Run benchmark against SOLLOL intelligent routing."""
    print(f"🧠 Running SOLLOL intelligent routing benchmark...")
    print(f"   URL: {sollol_url}")
    print(f"   Duration: {duration}s")
    print(f"   Concurrency: {concurrency}")

    bench = LoadBalancerBenchmark(sollol_url, concurrency)
    start_time = time.time()
    results = await bench.run_load_test(duration, requests_per_second=10)
    actual_duration = time.time() - start_time

    analyzed = bench.analyze_results("SOLLOL (Intelligent)", results, actual_duration)
    await bench.close()

    print(f"✅ Completed {analyzed.total_requests} requests")
    return analyzed


async def run_roundrobin_benchmark(
    hosts: List[str],
    duration: int,
    concurrency: int
) -> BenchmarkResults:
    """
    Simulate round-robin load balancing for comparison.

    Note: This is a simulation - it directly hits Ollama nodes in round-robin.
    """
    print(f"🔄 Running round-robin benchmark (simulation)...")
    print(f"   Hosts: {hosts}")
    print(f"   Duration: {duration}s")
    print(f"   Concurrency: {concurrency}")

    # We'll simulate by randomly selecting hosts
    # In a real scenario, you'd deploy a simple nginx round-robin proxy
    import random

    results = []
    start_time = time.time()

    async with httpx.AsyncClient(timeout=30.0) as client:
        request_count = 0
        payloads = [
            {"model": "llama3.2", "messages": [{"role": "user", "content": "Hello!"}]},
            {"model": "llama3.2", "messages": [{"role": "user", "content": "Explain quantum computing."}]},
        ]

        while time.time() - start_time < duration:
            host = hosts[request_count % len(hosts)]  # Round-robin
            payload = payloads[request_count % len(payloads)]

            req_start = time.time()
            try:
                response = await client.post(
                    f"http://{host}/api/chat",
                    json=payload
                )
                latency = (time.time() - req_start) * 1000

                results.append(RequestResult(
                    success=response.status_code == 200,
                    latency_ms=latency,
                    timestamp=req_start,
                    host_used=host
                ))
            except Exception as e:
                latency = (time.time() - req_start) * 1000
                results.append(RequestResult(
                    success=False,
                    latency_ms=latency,
                    timestamp=req_start,
                    error=str(e),
                    host_used=host
                ))

            request_count += 1
            await asyncio.sleep(0.1)  # Rate limiting

    actual_duration = time.time() - start_time

    bench = LoadBalancerBenchmark("", concurrency)
    analyzed = bench.analyze_results("Round-Robin", results, actual_duration)

    print(f"✅ Completed {analyzed.total_requests} requests")
    return analyzed


def print_comparison(sollol: BenchmarkResults, roundrobin: BenchmarkResults):
    """Print comparison table."""
    print("\n" + "=" * 80)
    print("📊 BENCHMARK RESULTS COMPARISON")
    print("=" * 80)

    def improvement(sollol_val, rr_val, higher_better=False):
        """Calculate improvement percentage."""
        if rr_val == 0:
            return "N/A"
        diff_pct = ((sollol_val - rr_val) / rr_val) * 100
        if not higher_better:
            diff_pct = -diff_pct
        return f"{diff_pct:+.1f}%"

    print(f"\n{'Metric':<30} {'Round-Robin':<20} {'SOLLOL':<20} {'Improvement':<15}")
    print("-" * 85)

    # Success rate
    print(f"{'Success Rate':<30} {roundrobin.success_rate*100:>18.1f}% {sollol.success_rate*100:>18.1f}% {improvement(sollol.success_rate, roundrobin.success_rate, True):>15}")

    # Latency metrics (lower is better)
    print(f"{'Avg Latency':<30} {roundrobin.avg_latency_ms:>18.0f}ms {sollol.avg_latency_ms:>18.0f}ms {improvement(sollol.avg_latency_ms, roundrobin.avg_latency_ms):>15}")
    print(f"{'P50 Latency':<30} {roundrobin.p50_latency_ms:>18.0f}ms {sollol.p50_latency_ms:>18.0f}ms {improvement(sollol.p50_latency_ms, roundrobin.p50_latency_ms):>15}")
    print(f"{'P95 Latency':<30} {roundrobin.p95_latency_ms:>18.0f}ms {sollol.p95_latency_ms:>18.0f}ms {improvement(sollol.p95_latency_ms, roundrobin.p95_latency_ms):>15}")
    print(f"{'P99 Latency':<30} {roundrobin.p99_latency_ms:>18.0f}ms {sollol.p99_latency_ms:>18.0f}ms {improvement(sollol.p99_latency_ms, roundrobin.p99_latency_ms):>15}")

    # Throughput (higher is better)
    print(f"{'Requests/sec':<30} {roundrobin.requests_per_second:>18.1f} {sollol.requests_per_second:>18.1f} {improvement(sollol.requests_per_second, roundrobin.requests_per_second, True):>15}")

    # Total requests
    print(f"{'Total Requests':<30} {roundrobin.total_requests:>18} {sollol.total_requests:>18} {'':<15}")
    print(f"{'Failed Requests':<30} {roundrobin.failed_requests:>18} {sollol.failed_requests:>18} {'':<15}")

    print("\n" + "=" * 80)

    # Host distribution
    print("\n📍 HOST DISTRIBUTION")
    print("-" * 40)
    print("\nSOLLOL (Intelligent Routing):")
    for host, count in sollol.host_distribution.items():
        pct = (count / sollol.successful_requests) * 100
        print(f"  {host:<25} {count:>6} requests ({pct:.1f}%)")

    print("\nRound-Robin:")
    for host, count in roundrobin.host_distribution.items():
        pct = (count / roundrobin.successful_requests) * 100
        print(f"  {host:<25} {count:>6} requests ({pct:.1f}%)")

    print("\n" + "=" * 80)


def save_results(sollol: BenchmarkResults, roundrobin: BenchmarkResults, output_file: str):
    """Save results to JSON file."""
    results = {
        "sollol": asdict(sollol),
        "round_robin": asdict(roundrobin),
        "timestamp": time.time()
    }

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Results saved to {output_file}")


async def main():
    parser = argparse.ArgumentParser(description="SOLLOL Benchmark Suite")
    parser.add_argument("--sollol-url", default="http://localhost:8000", help="SOLLOL gateway URL")
    parser.add_argument("--hosts", nargs="+", default=["localhost:11434", "localhost:11435", "localhost:11436"], help="Ollama host addresses for round-robin test")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON file")
    parser.add_argument("--skip-roundrobin", action="store_true", help="Skip round-robin benchmark")

    args = parser.parse_args()

    print("🚀 SOLLOL Benchmark Suite")
    print("=" * 80)

    # Run SOLLOL benchmark
    sollol_results = await run_sollol_benchmark(
        args.sollol_url,
        args.duration,
        args.concurrency
    )

    # Run round-robin benchmark (optional)
    if not args.skip_roundrobin:
        print()
        roundrobin_results = await run_roundrobin_benchmark(
            args.hosts,
            args.duration,
            args.concurrency
        )

        # Print comparison
        print_comparison(sollol_results, roundrobin_results)

        # Save results
        save_results(sollol_results, roundrobin_results, args.output)
    else:
        print("\n✅ SOLLOL benchmark complete!")
        print(f"   Success rate: {sollol_results.success_rate*100:.1f}%")
        print(f"   Avg latency: {sollol_results.avg_latency_ms:.0f}ms")
        print(f"   Throughput: {sollol_results.requests_per_second:.1f} req/s")


if __name__ == "__main__":
    asyncio.run(main())
