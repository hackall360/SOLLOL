# Benchmark Results

This directory contains real performance benchmark results from SOLLOL testing.

## Available Benchmarks

### Single-Node Ollama Performance

**File:** `ollama_benchmark_llama3.2_1759757430.json`

**Test Configuration:**
- **Date:** 2025-10-06
- **Model:** llama3.2 (3B parameters)
- **Requests:** 50 total requests
- **Concurrency:** 5 concurrent requests
- **Hardware:** Single Ollama node on localhost

**Results:**
- **Success Rate:** 100.0%
- **Throughput:** 0.51 requests/second
- **Average Latency:** 5658.8 ms
- **P95 Latency:** 11298.7 ms
- **P99 Latency:** 12258.6 ms

## How to Run Benchmarks

### Basic Single-Node Test

```bash
# Test llama3.2 with 50 requests
python benchmarks/simple_ollama_benchmark.py llama3.2 50

# Test different model
python benchmarks/simple_ollama_benchmark.py mistral 100
```

### Full Load Balancer Comparison

```bash
# Requires SOLLOL gateway running + multiple Ollama nodes
python benchmarks/run_benchmarks.py \
  --sollol-url http://localhost:8000 \
  --hosts localhost:11434 localhost:11435 \
  --duration 60 \
  --concurrency 10
```

## Interpreting Results

All benchmark results are saved as JSON with the following structure:

```json
{
  "benchmark_config": {
    "base_url": "http://localhost:11434",
    "model": "llama3.2",
    "num_requests": 50,
    "concurrency": 5,
    "duration_seconds": 97.19
  },
  "results": {
    "total_requests": 50,
    "successful_requests": 50,
    "failed_requests": 0,
    "success_rate": 1.0,
    "requests_per_second": 0.51
  },
  "latency_ms": {
    "min": 680.9,
    "max": 12258.6,
    "avg": 5658.8,
    "median": 5293.6,
    "p50": 5293.6,
    "p95": 11298.7,
    "p99": 12258.6
  }
}
```

## Hardware Specifications

Current test environment:
- **Platform:** Linux 6.16.3
- **Ollama:** Version with 75+ models loaded
- **Test Node:** localhost:11434

## Next Steps

To validate SOLLOL's intelligent routing benefits, run:

1. Set up multiple Ollama nodes
2. Start SOLLOL gateway
3. Run comparative benchmarks showing SOLLOL vs round-robin
4. Document improvements in routing efficiency

## Contributing Benchmarks

If you run benchmarks on your hardware:
1. Run the benchmark scripts
2. Save results to this directory
3. Document your hardware specs
4. Submit a PR with your findings
