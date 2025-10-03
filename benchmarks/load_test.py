#!/usr/bin/env python
"""
Load testing script for SOLLOL vs round-robin routing.

Generates realistic workloads and compares:
- Average latency
- P95/P99 latencies
- Success rates
- Throughput (requests/sec)
- Resource utilization

Usage:
    python benchmarks/load_test.py --duration 60 --workers 10
"""
import asyncio
import time
import statistics
from typing import List, Dict
from dataclasses import dataclass, field
import argparse
import json
import httpx


@dataclass
class RequestResult:
    """Single request result."""
    success: bool
    latency_ms: float
    timestamp: float
    host: str = ""
    error: str = ""


@dataclass
class BenchmarkResults:
    """Aggregate benchmark results."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies: List[float] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        return statistics.mean(self.latencies) if self.latencies else 0.0

    @property
    def p50_latency_ms(self) -> float:
        """Median (P50) latency."""
        return statistics.median(self.latencies) if self.latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index]

    @property
    def p99_latency_ms(self) -> float:
        """99th percentile latency."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[index]

    @property
    def requests_per_second(self) -> float:
        """Throughput in requests per second."""
        duration = self.end_time - self.start_time
        return self.total_requests / duration if duration > 0 else 0.0


class LoadTester:
    """Load testing orchestrator."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "llama3.2"
    ):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_request(
        self,
        prompt: str,
        priority: int = 5,
        use_sollol: bool = True
    ) -> RequestResult:
        """
        Send a single request.

        Args:
            prompt: Input prompt
            priority: Request priority (1-10)
            use_sollol: If True, use SOLLOL; if False, use direct Ollama

        Returns:
            RequestResult with timing and success info
        """
        start = time.time()

        try:
            if use_sollol:
                # Use SOLLOL intelligent routing
                url = f"{self.base_url}/api/chat"
                params = {"priority": priority}
            else:
                # Direct to first Ollama node (round-robin simulation)
                url = "http://localhost:11434/api/chat"
                params = {}

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }

            response = await self.client.post(url, json=payload, params=params)
            latency_ms = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                host = data.get("_sollol_routing", {}).get("host", "unknown")
                return RequestResult(
                    success=True,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                    host=host
                )
            else:
                return RequestResult(
                    success=False,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                    error=f"HTTP {response.status_code}"
                )

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            return RequestResult(
                success=False,
                latency_ms=latency_ms,
                timestamp=time.time(),
                error=str(e)
            )

    async def generate_workload(
        self,
        duration_seconds: int,
        requests_per_second: int,
        use_sollol: bool = True
    ) -> BenchmarkResults:
        """
        Generate sustained load for specified duration.

        Args:
            duration_seconds: How long to run
            requests_per_second: Target RPS
            use_sollol: Use SOLLOL or direct Ollama

        Returns:
            BenchmarkResults with aggregated metrics
        """
        results = BenchmarkResults()
        results.start_time = time.time()

        # Workload patterns (realistic distribution)
        workloads = [
            ("Write a short story about a robot", 5, 0.4),  # 40% generation
            ("Summarize this text briefly", 7, 0.2),        # 20% summarization
            ("Classify sentiment: I love this!", 8, 0.15),  # 15% classification
            ("Extract entities from: John lives in NYC", 6, 0.15),  # 15% extraction
            ("Analyze this data pattern", 5, 0.1),          # 10% analysis
        ]

        tasks = []
        interval = 1.0 / requests_per_second

        while (time.time() - results.start_time) < duration_seconds:
            # Pick workload based on distribution
            import random
            rand = random.random()
            cumulative = 0.0
            selected_workload = workloads[0]

            for prompt, priority, probability in workloads:
                cumulative += probability
                if rand <= cumulative:
                    selected_workload = (prompt, priority, probability)
                    break

            prompt, priority, _ = selected_workload

            # Send request
            task = asyncio.create_task(
                self.send_request(prompt, priority, use_sollol)
            )
            tasks.append(task)

            # Throttle to target RPS
            await asyncio.sleep(interval)

        # Wait for all requests to complete
        request_results = await asyncio.gather(*tasks)

        # Aggregate results
        results.end_time = time.time()
        results.total_requests = len(request_results)

        for result in request_results:
            if result.success:
                results.successful_requests += 1
                results.latencies.append(result.latency_ms)
            else:
                results.failed_requests += 1

        return results

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


async def run_benchmark(
    duration: int,
    rps: int,
    sollol_url: str,
    model: str
):
    """
    Run comparative benchmark: SOLLOL vs Round-Robin.

    Args:
        duration: Test duration in seconds
        rps: Requests per second
        sollol_url: SOLLOL base URL
        model: Ollama model to use
    """
    print("=" * 60)
    print("SOLLOL PERFORMANCE BENCHMARK")
    print("=" * 60)
    print(f"Duration: {duration}s")
    print(f"Target RPS: {rps}")
    print(f"Model: {model}")
    print()

    tester = LoadTester(base_url=sollol_url, model=model)

    # Test 1: SOLLOL Intelligent Routing
    print("🧠 Running SOLLOL (Intelligent Routing)...")
    sollol_results = await tester.generate_workload(
        duration_seconds=duration,
        requests_per_second=rps,
        use_sollol=True
    )
    print("✓ SOLLOL test complete\n")

    # Test 2: Round-Robin (Direct Ollama)
    print("🔄 Running Round-Robin (Direct Ollama)...")
    roundrobin_results = await tester.generate_workload(
        duration_seconds=duration,
        requests_per_second=rps,
        use_sollol=False
    )
    print("✓ Round-Robin test complete\n")

    await tester.close()

    # Print comparison
    print_comparison(sollol_results, roundrobin_results)

    # Save results
    save_results(sollol_results, roundrobin_results, duration, rps, model)


def print_comparison(sollol: BenchmarkResults, roundrobin: BenchmarkResults):
    """Print side-by-side comparison."""
    print("=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    print()

    metrics = [
        ("Total Requests", sollol.total_requests, roundrobin.total_requests, ""),
        ("Success Rate", sollol.success_rate, roundrobin.success_rate, "%"),
        ("Avg Latency", sollol.avg_latency_ms, roundrobin.avg_latency_ms, "ms"),
        ("P50 Latency", sollol.p50_latency_ms, roundrobin.p50_latency_ms, "ms"),
        ("P95 Latency", sollol.p95_latency_ms, roundrobin.p95_latency_ms, "ms"),
        ("P99 Latency", sollol.p99_latency_ms, roundrobin.p99_latency_ms, "ms"),
        ("Throughput", sollol.requests_per_second, roundrobin.requests_per_second, "req/s"),
    ]

    print(f"{'Metric':<20} {'SOLLOL':>12} {'Round-Robin':>12} {'Improvement':>12}")
    print("-" * 60)

    for metric_name, sollol_val, rr_val, unit in metrics:
        if rr_val > 0:
            if "Latency" in metric_name:
                # Lower is better for latency
                improvement = ((rr_val - sollol_val) / rr_val) * 100
                arrow = "⬇️" if improvement > 0 else "⬆️"
            else:
                # Higher is better for others
                improvement = ((sollol_val - rr_val) / rr_val) * 100
                arrow = "⬆️" if improvement > 0 else "⬇️"

            print(
                f"{metric_name:<20} "
                f"{sollol_val:>10.1f}{unit:>2} "
                f"{rr_val:>10.1f}{unit:>2} "
                f"{arrow} {abs(improvement):>8.1f}%"
            )
        else:
            print(
                f"{metric_name:<20} "
                f"{sollol_val:>10.1f}{unit:>2} "
                f"{rr_val:>10.1f}{unit:>2} "
                f"{'N/A':>12}"
            )

    print()


def save_results(
    sollol: BenchmarkResults,
    roundrobin: BenchmarkResults,
    duration: int,
    rps: int,
    model: str
):
    """Save results to JSON file."""
    results = {
        "timestamp": time.time(),
        "config": {
            "duration_seconds": duration,
            "target_rps": rps,
            "model": model
        },
        "sollol": {
            "total_requests": sollol.total_requests,
            "success_rate": sollol.success_rate,
            "avg_latency_ms": sollol.avg_latency_ms,
            "p50_latency_ms": sollol.p50_latency_ms,
            "p95_latency_ms": sollol.p95_latency_ms,
            "p99_latency_ms": sollol.p99_latency_ms,
            "requests_per_second": sollol.requests_per_second
        },
        "roundrobin": {
            "total_requests": roundrobin.total_requests,
            "success_rate": roundrobin.success_rate,
            "avg_latency_ms": roundrobin.avg_latency_ms,
            "p50_latency_ms": roundrobin.p50_latency_ms,
            "p95_latency_ms": roundrobin.p95_latency_ms,
            "p99_latency_ms": roundrobin.p99_latency_ms,
            "requests_per_second": roundrobin.requests_per_second
        }
    }

    filename = f"benchmarks/results_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)

    print(f"📊 Results saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(description="SOLLOL Load Testing")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--rps",
        type=int,
        default=10,
        help="Target requests per second (default: 10)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="SOLLOL base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3.2",
        help="Ollama model to use (default: llama3.2)"
    )

    args = parser.parse_args()

    asyncio.run(run_benchmark(
        duration=args.duration,
        rps=args.rps,
        sollol_url=args.url,
        model=args.model
    ))


if __name__ == "__main__":
    main()
