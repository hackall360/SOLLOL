---
name: Performance Issue
about: Report performance degradation or optimization opportunities
title: '[PERF] '
labels: performance
assignees: ''
---

## Performance Issue

Brief description of the performance problem.

## Current Performance

- **Metric affected**: [e.g., latency, throughput, memory usage]
- **Current value**: [e.g., 2500ms avg latency]
- **Expected value**: [e.g., <1000ms avg latency]

## Environment

- **SOLLOL Version**: [e.g., v1.0.0]
- **Deployment**: [e.g., single node, distributed, cloud]
- **Hardware**:
  - Nodes: [e.g., 4 nodes]
  - CPU: [e.g., 32 cores per node]
  - RAM: [e.g., 64GB per node]
  - GPU: [e.g., RTX 3090 24GB]
- **Workload**:
  - Request rate: [e.g., 100 req/min]
  - Task distribution: [e.g., 60% generation, 30% embedding, 10% classification]

## Configuration

```python
# Your SOLLOL configuration
config = SOLLOLConfig(
    ray_workers=4,
    # ... other config
)
```

## Benchmarks

If you've run benchmarks, please share:

```
Metric: Value
Avg Latency: 2500ms
P95 Latency: 5000ms
Throughput: 45 req/min
CPU Utilization: 85%
GPU Utilization: 42%
```

## Profiling Data

(Optional) If you've profiled the issue, attach:
- Flame graphs
- cProfile output
- Ray dashboard screenshots
- Dask performance reports

## Reproduction

Steps to reproduce the performance issue:

1. Configure SOLLOL with [...]
2. Send workload [...]
3. Measure [...]
4. Observe degradation

## Expected Behavior

What performance characteristics would you expect?

## Additional Context

- Network latency between nodes
- Model sizes being used
- Input/output payload sizes
- Any patterns observed (e.g., degrades over time, specific request types slow)

## Proposed Optimizations

(Optional) Ideas for improving performance:

- [ ] Caching
- [ ] Algorithm optimization
- [ ] Better resource allocation
- [ ] Other: [describe]
