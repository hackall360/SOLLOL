# SOLLOL Documentation

<div align="center" markdown>

[![Tests Passing](https://img.shields.io/badge/tests-57%20passing-success?style=for-the-badge&logo=pytest)](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](https://github.com/BenevolentJoker-JohnL/SOLLOL/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)

**Production-Ready Intelligent Load Balancing for Ollama Clusters**

[Quick Start](getting-started/quick-start.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/BenevolentJoker-JohnL/SOLLOL){ .md-button }

</div>

---

## What is SOLLOL?

**SOLLOL transforms multiple Ollama nodes into a unified, intelligent AI inference cluster.**

Instead of manually managing multiple Ollama instances or using simple round-robin load balancing, SOLLOL analyzes each request's requirements and automatically routes it to the optimal node based on:

- **Task complexity** (embedding vs generation vs analysis)
- **Resource availability** (GPU memory, CPU load)
- **Real-time performance** (latency, success rate)
- **Historical patterns** (adaptive learning from past executions)

## Key Features

<div class="grid cards" markdown>

-   :material-brain:{ .lg .middle } **Intelligent Routing**

    ---

    Context-aware analysis routes requests to optimal nodes using multi-factor scoring and adaptive learning.

    [:octicons-arrow-right-24: Learn more](architecture/routing.md)

-   :material-priority-high:{ .lg .middle } **Priority Queue**

    ---

    10-level priority system with age-based fairness ensures critical tasks get resources without starvation.

    [:octicons-arrow-right-24: Learn more](architecture/priority.md)

-   :material-sync:{ .lg .middle } **Auto Failover**

    ---

    3 retry attempts with exponential backoff and health monitoring ensure zero-downtime operation.

    [:octicons-arrow-right-24: Learn more](architecture/failover.md)

-   :material-chart-line:{ .lg .middle } **Observability**

    ---

    Real-time dashboard with Prometheus metrics and routing transparency for complete visibility.

    [:octicons-arrow-right-24: Learn more](features/observability.md)

-   :material-lightning-bolt:{ .lg .middle } **High Performance**

    ---

    Ray actors and Dask batch processing deliver <10ms routing overhead with 40-60% throughput gains.

    [:octicons-arrow-right-24: Learn more](features/performance.md)

-   :material-security:{ .lg .middle } **Enterprise Security**

    ---

    SHA-256 API keys with RBAC permissions and per-key rate limiting for production deployments.

    [:octicons-arrow-right-24: Learn more](features/security.md)

</div>

## Performance Impact

| Metric | Expected Improvement |
|--------|---------------------|
| **Avg Latency** | **-30-40%** (context-aware routing to optimal nodes) |
| **P95 Latency** | **-40-50%** (avoiding overloaded nodes) |
| **Success Rate** | **+2-4pp** (automatic failover and retry) |
| **Throughput** | **+40-60%** (better resource utilization) |
| **GPU Utilization** | **+50-80%** (intelligent task-to-GPU matching) |

!!! success "Production Ready"
    SOLLOL is fully functional and production-ready. No artificial limits, no feature gates.

## Quick Links

- [**Quick Start Guide**](getting-started/quick-start.md) - Get up and running in 5 minutes
- [**Architecture Overview**](architecture/overview.md) - Understand the system design
- [**Deployment Guide**](deployment/docker.md) - Deploy with Docker or Kubernetes
- [**Benchmarks**](benchmarks/overview.md) - See performance methodology and results
- [**API Reference**](api/rest.md) - Complete API documentation

## Community & Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/BenevolentJoker-JohnL/SOLLOL/issues)
- **Discussions**: [Ask questions or share ideas](https://github.com/BenevolentJoker-JohnL/SOLLOL/discussions)
- **Contributing**: [See contribution guidelines](contributing/guidelines.md)
- **Enterprise**: [Explore enterprise features](enterprise/roadmap.md)

---

<div align="center" markdown>

**Built with :heart: by [BenevolentJoker-JohnL](https://github.com/BenevolentJoker-JohnL)**

[GitHub](https://github.com/BenevolentJoker-JohnL/SOLLOL){ .md-button }
[Sponsor](https://github.com/sponsors/BenevolentJoker-JohnL){ .md-button .md-button--primary }

</div>
