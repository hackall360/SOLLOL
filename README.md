# SOLLOL - Production-Ready Orchestration for Local LLM Clusters

<div align="center">

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml/badge.svg)](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/BenevolentJoker-JohnL/SOLLOL/branch/main/graph/badge.svg)](https://codecov.io/gh/BenevolentJoker-JohnL/SOLLOL)

**Open-source orchestration layer that combines intelligent task routing with distributed model inference for local LLM clusters.**

[Quick Start](#quick-start) • [Features](#why-sollol) • [Architecture](#architecture) • [Documentation](#documentation) • [Examples](#examples)

</div>

---

## 🎯 What is SOLLOL?

SOLLOL (Super Ollama Load balancer & Orchestration Layer) transforms your collection of Ollama nodes into an **intelligent AI cluster** with adaptive routing and automatic failover—all running on your own hardware.

### The Problem

You have multiple machines with GPUs running Ollama, but:
- ❌ Manual node selection for each request
- ❌ No way to run models larger than your biggest GPU
- ❌ Can't distribute multi-agent workloads efficiently
- ❌ No automatic failover or load balancing
- ❌ Zero visibility into cluster performance

### The SOLLOL Solution

SOLLOL provides:
- ✅ **Intelligent routing** that learns which nodes work best for each task
- ✅ **Model sharding** to run 70B+ models across multiple machines
- ✅ **Parallel agent execution** for multi-agent frameworks
- ✅ **Auto-discovery** of all nodes and capabilities
- ✅ **Built-in observability** with real-time metrics
- ✅ **Zero-config deployment** - just point and go

---

## 🚀 Why SOLLOL?

### 1. **Two Distribution Modes in One System**

SOLLOL combines both task distribution and model sharding:

#### 📊 Task Distribution (Horizontal Scaling)
Distribute **multiple requests** across your cluster in parallel:
```python
# Run 10 agents simultaneously across 5 nodes
pool = OllamaPool.auto_configure()
responses = await asyncio.gather(*[
    pool.chat(model="llama3.2", messages=[...])
    for _ in range(10)
])
# Parallel execution across available nodes
```

#### 🧩 Model Sharding (Vertical Scaling)
Run **single large models** that don't fit on one machine:
```python
# Run larger models across multiple nodes
# Note: Verified with 13B across 2-3 nodes; larger models not extensively tested
router = HybridRouter(
    enable_distributed=True,
    num_rpc_backends=4
)
response = await router.route_request(
    model="llama3:70b",  # Sharded automatically
    messages=[...]
)
```

**Use them together!** Small models use task distribution, large models use sharding.

---

### 2. **Intelligent, Not Just Balanced**

SOLLOL doesn't just distribute requests randomly—it **learns** and **optimizes**:

| Feature | Simple Load Balancer | SOLLOL |
|---------|---------------------|---------|
| **Routing** | Round-robin | Context-aware scoring |
| **Learning** | None | Adapts from performance history |
| **Resource Awareness** | None | GPU/CPU/memory-aware |
| **Task Optimization** | None | Routes by task type complexity |
| **Failover** | Manual | Automatic with health checks |
| **Priority** | FIFO | Priority queue with fairness |

**Example**: SOLLOL automatically routes:
- Heavy generation tasks → GPU nodes with 24GB VRAM
- Fast embeddings → CPU nodes or smaller GPUs
- Critical requests → Fastest, most reliable nodes
- Batch processing → Lower priority, distributed load

---

### 3. **Production-Ready from Day One**

```python
from sollol import SOLLOL, SOLLOLConfig

# Literally 3 lines to production
config = SOLLOLConfig.auto_discover()
sollol = SOLLOL(config)
sollol.start()  # ✅ Gateway running on :8000
```

**Out of the box**:
- Auto-discovery of Ollama nodes
- Health monitoring and failover
- Prometheus metrics
- Web dashboard
- Connection pooling
- Request hedging
- Priority queuing

---

## 🏗️ Architecture

### High-Level Overview

```
┌────────────────────────────────────────────────────────┐
│                  Your Application                       │
│         (SynapticLlamas, custom agents, etc.)          │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│                 SOLLOL Gateway (:8000)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Intelligent Routing Engine               │  │
│  │  • Analyzes: task type, complexity, resources    │  │
│  │  • Scores: all nodes based on context            │  │
│  │  • Learns: from performance history              │  │
│  │  • Routes: to optimal node                       │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Priority Queue + Failover               │  │
│  └──────────────────────────────────────────────────┘  │
└────────┬─────────────────────────┬─────────────────────┘
         │                         │
         ▼                         ▼
  ┌─────────────┐          ┌──────────────┐
  │ Task Mode   │          │  Shard Mode  │
  │ Ray Cluster │          │  llama.cpp   │
  └──────┬──────┘          └──────┬───────┘
         │                         │
         ▼                         ▼
┌────────────────────────────────────────────────────────┐
│              Your Heterogeneous Cluster                 │
│  GPU (24GB) │ GPU (16GB) │ CPU (64c) │ GPU (8GB) │...  │
└────────────────────────────────────────────────────────┘
```

### How Routing Works

```python
# 1. Request arrives
POST /api/chat {
  "model": "llama3.2",
  "messages": [{"role": "user", "content": "Complex analysis task..."}],
  "priority": 8
}

# 2. SOLLOL analyzes
task_type = "generation"       # Auto-detected
complexity = "high"             # Token count analysis
requires_gpu = True             # Based on task
estimated_duration = 3.2s       # From history

# 3. SOLLOL scores all nodes
Node A (GPU 24GB, load: 0.2, latency: 120ms) → Score: 185.3 ✓ WINNER
Node B (GPU 8GB,  load: 0.6, latency: 200ms) → Score: 92.1
Node C (CPU only, load: 0.1, latency: 80ms)  → Score: 41.2

# 4. Routes to Node A, monitors execution, learns for next time
```

**Scoring Algorithm**:
```
Score = 100.0 (baseline)
      × success_rate (0.0-1.0)
      ÷ (1 + latency_penalty)
      × gpu_bonus (1.5x if GPU available & needed)
      ÷ (1 + load_penalty)
      × priority_alignment
      × task_specialization
```

---

## 📦 Installation

### Quick Install (PyPI)
```bash
pip install sollol
```

### From Source
```bash
git clone https://github.com/BenevolentJoker-JohnL/SOLLOL.git
cd SOLLOL
pip install -e .
```

---

## ⚡ Quick Start

### 1. Synchronous API (No async/await needed!)

**New in v0.3.6:** SOLLOL now provides a synchronous API for easier integration with non-async applications.

```python
from sollol.sync_wrapper import OllamaPool
from sollol.priority_helpers import Priority

# Auto-discover and connect to all Ollama nodes
pool = OllamaPool.auto_configure()

# Make requests - SOLLOL routes intelligently
# No async/await needed!
response = pool.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}],
    priority=Priority.HIGH,  # Semantic priority levels
    timeout=60  # Request timeout in seconds
)

print(response['message']['content'])
print(f"Routed to: {response.get('_sollol_routing', {}).get('host', 'unknown')}")
```

**Key features of synchronous API:**
- ✅ No async/await syntax required
- ✅ Works with synchronous agent frameworks
- ✅ Same intelligent routing and features
- ✅ Runs async code in background thread automatically

---

### 2. Async API (Original)

For async applications, use the original async API:

```python
from sollol import OllamaPool

# Auto-discover and connect to all Ollama nodes
pool = await OllamaPool.auto_configure()

# Make requests - SOLLOL routes intelligently
response = await pool.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response['message']['content'])
print(f"Routed to: {response['_sollol_routing']['host']}")
print(f"Task type: {response['_sollol_routing']['task_type']}")
```

---

### 3. Priority-Based Multi-Agent Execution

**New in v0.3.6:** Use semantic priority levels and role-based mapping.

```python
from sollol.sync_wrapper import OllamaPool
from sollol.priority_helpers import Priority, get_priority_for_role

pool = OllamaPool.auto_configure()

# Define agents with different priorities
agents = [
    {"name": "Researcher", "role": "researcher"},  # Priority 8
    {"name": "Editor", "role": "editor"},          # Priority 6
    {"name": "Summarizer", "role": "summarizer"},  # Priority 5
]

for agent in agents:
    priority = get_priority_for_role(agent["role"])

    response = pool.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": f"Task for {agent['name']}"}],
        priority=priority
    )
    # User-facing agents get priority, background tasks wait
```

**Priority levels available:**
- `Priority.CRITICAL` (10) - Mission-critical
- `Priority.URGENT` (9) - Fast response needed
- `Priority.HIGH` (7) - Important tasks
- `Priority.NORMAL` (5) - Default
- `Priority.LOW` (3) - Background tasks
- `Priority.BATCH` (1) - Can wait

---

### 4. Model Sharding with llama.cpp (Large Models)

**Run models larger than your biggest GPU** by distributing layers across multiple machines.

#### When to Use Model Sharding

Use model sharding when:
- ✅ Model doesn't fit on your largest GPU (e.g., 70B models on 16GB GPUs)
- ✅ You have multiple machines with network connectivity
- ✅ You can tolerate slower inference for capability

Don't use sharding when:
- ❌ Model fits on a single GPU (use task distribution instead)
- ❌ You need maximum inference speed
- ❌ Network latency is high (>10ms between machines)

#### Quick Start: Auto-Setup (Easiest)

```python
from sollol.sync_wrapper import HybridRouter, OllamaPool

# SOLLOL handles all setup automatically
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,  # Enable model sharding
    auto_setup_rpc=True,      # Auto-configure RPC backends
    num_rpc_backends=3        # Distribute across 3 machines
)

# Use large model that doesn't fit on one machine
response = router.route_request(
    model="llama3.1:70b",  # Automatically sharded across backends
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)

print(response['message']['content'])
```

**What happens automatically:**
1. SOLLOL discovers available RPC backends on your network
2. Extracts the GGUF model from Ollama storage
3. Starts llama-server coordinator with optimal settings
4. Distributes model layers across backends
5. Routes your request to the coordinator

#### Architecture: How It Works

```
┌────────────────────────────────────────────┐
│    Llama 3.1 70B Model (40GB total)        │
│           Distributed Sharding             │
└────────────────────────────────────────────┘
                    │
       ┌────────────┼────────────┐
       │            │            │
       ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Machine 1   │ │  Machine 2   │ │  Machine 3   │
│ Layers 0-26  │ │ Layers 27-53 │ │ Layers 54-79 │
│   (~13GB)    │ │   (~13GB)    │ │   (~13GB)    │
│ RPC Backend  │ │ RPC Backend  │ │ RPC Backend  │
└──────────────┘ └──────────────┘ └──────────────┘
       ▲            ▲            ▲
       └────────────┼────────────┘
                    │
         ┌──────────┴──────────┐
         │ llama-server        │
         │ Coordinator         │
         │ (Port 18080)        │
         └─────────────────────┘
```

#### Manual Setup (Advanced)

For explicit control over RPC backends:

```python
from sollol.llama_cpp_coordinator import LlamaCppCoordinator
from sollol.rpc_registry import RPCBackendRegistry

# 1. Register RPC backends explicitly
registry = RPCBackendRegistry()
registry.add_backend("rpc_1", "grpc://10.9.66.45:50052")
registry.add_backend("rpc_2", "grpc://10.9.66.46:50052")
registry.add_backend("rpc_3", "grpc://10.9.66.47:50052")

# 2. Create coordinator
coordinator = LlamaCppCoordinator(
    coordinator_port=18080,
    rpc_backends=registry.get_all_backends(),
    context_size=4096,
    gpu_layers=-1  # Use all available GPU layers
)

# 3. Start and use
await coordinator.start(model_name="llama3.1:70b")
response = await coordinator.generate(
    prompt="Explain the theory of relativity",
    max_tokens=500
)
```

#### Performance Expectations

| Model Size | Single GPU | Sharded (3 nodes) | Trade-off |
|------------|-----------|-------------------|-----------|
| **13B** | ✅ 20 tok/s | ✅ 5 tok/s | -75% speed, works on 3×smaller GPUs |
| **70B** | ❌ OOM | ⚠️ 3-5 tok/s (est.) | Enables model that won't run otherwise |

**Trade-offs:**
- 🐌 **Startup**: 2-5 minutes (model distribution + loading)
- 🐌 **Inference**: ~4x slower than local (network overhead)
- ✅ **Capability**: Run models that won't fit on single GPU

**Learn More:**
- 📖 [Complete llama.cpp Guide](docs/llama_cpp_guide.md) - Setup, optimization, troubleshooting
- 💻 [Working Examples](examples/llama_cpp_distributed.py) - 5 complete examples including conversation, batch processing, error handling

### 5. SOLLOL Detection

**New in v0.3.6:** Detect if SOLLOL is running vs native Ollama.

```python
import requests

def is_sollol(url="http://localhost:11434"):
    """Check if SOLLOL is running at the given URL."""

    # Method 1: Check X-Powered-By header
    response = requests.get(url)
    if response.headers.get("X-Powered-By") == "SOLLOL":
        return True

    # Method 2: Check health endpoint
    response = requests.get(f"{url}/api/health")
    data = response.json()
    if data.get("service") == "SOLLOL":
        return True

    return False

# Use it
if is_sollol("http://localhost:11434"):
    print("✓ SOLLOL detected - using intelligent routing")
else:
    print("Native Ollama detected")
```

**Why this matters:**
- Enables graceful fallback in client applications
- Makes SOLLOL a true drop-in replacement
- Clients can auto-detect and use SOLLOL features when available

---

### 6. Production Gateway

```python
from sollol import SOLLOL, SOLLOLConfig

# Full production setup
config = SOLLOLConfig(
    ray_workers=4,
    dask_workers=2,
    hosts=["gpu-1:11434", "gpu-2:11434", "cpu-1:11434"],
    gateway_port=8000,
    metrics_port=9090
)

sollol = SOLLOL(config)
sollol.start()  # Blocks and runs gateway

# Access via HTTP:
# curl http://localhost:8000/api/chat -d '{...}'
# curl http://localhost:8000/api/stats
# curl http://localhost:8000/api/dashboard
```

---

## 🎓 Use Cases

### 1. Multi-Agent AI Systems (SynapticLlamas, CrewAI, AutoGPT)

**Problem**: Running 10 agents sequentially takes 10x longer than necessary.

**Solution**: SOLLOL distributes agents across nodes in parallel.

```python
# Before: Sequential execution on one node
# After: Parallel execution with SOLLOL
pool = OllamaPool.auto_configure()
agents = await asyncio.gather(*[
    pool.chat(model="llama3.2", messages=agent_prompts[i])
    for i in range(10)
])
# Speedup depends on number of available nodes and their capacity
```

### 2. Large Model Inference

**Problem**: Your model doesn't fit in available VRAM.

**Solution**: SOLLOL can shard models across multiple machines via llama.cpp.

```python
# Distribute model across multiple nodes
# Note: Verified with 13B models; larger models not extensively tested
router = HybridRouter(
    enable_distributed=True,
    num_rpc_backends=4
)
# Trade-off: Slower startup/inference but enables running larger models
```

### 3. Mixed Workloads

**Problem**: Different tasks need different resources.

**Solution**: SOLLOL routes each task to the optimal node.

```python
pool = OllamaPool.auto_configure()

# Heavy generation → GPU node
chat = pool.chat(model="llama3.2:70b", messages=[...])

# Fast embeddings → CPU node
embeddings = pool.embed(model="nomic-embed-text", input=[...])

# SOLLOL automatically routes each to the best available node
```

### 4. High Availability Production

**Problem**: Node failures break your service.

**Solution**: SOLLOL auto-fails over and recovers.

```python
# Node A fails mid-request
# ✅ SOLLOL automatically:
# 1. Detects failure
# 2. Retries on Node B
# 3. Marks Node A as degraded
# 4. Periodically re-checks Node A
# 5. Restores Node A when healthy
```

---

## 📊 Performance & Benchmarks

### Validation Status

**What's Been Validated ✅**
- Single-node baseline performance measured
- Code exists and is reviewable (75+ modules)
- Tests pass in CI (57 tests, coverage tracked)
- Architecture implements intelligent routing

**What Needs Validation ⚠️**
- Comparative benchmarks (SOLLOL vs round-robin)
- Multi-node performance improvements
- Real-world latency/throughput gains

📖 **See [BENCHMARKING.md](BENCHMARKING.md) for complete validation roadmap and how to run comparative tests.**

---

### Measured Baseline Performance

**Single Ollama Node** (llama3.2-3B, 50 requests, concurrency=5):
- ✅ **Success Rate:** 100%
- ⚡ **Throughput:** 0.51 req/s
- 📈 **Average Latency:** 5,659 ms
- 📈 **P95 Latency:** 11,299 ms
- 📈 **P99 Latency:** 12,259 ms

**Hardware:** Single Ollama instance with 75+ models loaded
**Data:** See [`benchmarks/results/`](benchmarks/results/) for raw JSON

**Run Your Own:**
```bash
# Baseline test (no cluster needed)
python benchmarks/simple_ollama_benchmark.py llama3.2 50

# Comparative test (requires docker-compose)
docker-compose up -d
python benchmarks/run_benchmarks.py --sollol-url http://localhost:8000 --duration 60
```

---

### Projected Performance (Unvalidated)

**Note:** These are architectural projections, not measured results. Requires multi-node cluster setup for validation.

**Theory:** With N nodes and parallelizable workload:
- Task distribution can approach N× parallelization (limited by request rate)
- Intelligent routing should reduce tail latencies vs random selection
- Resource-aware placement reduces contention and failures

**Reality:** Requires multi-node cluster validation. See [BENCHMARKING.md](BENCHMARKING.md) for test procedure and [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) for implementation details.

### Model Sharding Performance

| Model | Single 24GB GPU | SOLLOL (3×16GB) | Status |
|-------|----------------|-----------------|-----------|
| **13B** | ✅ ~20 tok/s | ✅ ~5 tok/s | ✅ Verified working |
| **70B** | ❌ OOM | ⚠️ Estimated ~3-5 tok/s | ⚠️ Not extensively tested |

**When to use sharding**: When model doesn't fit on your largest GPU. You trade speed for capability.

**Performance trade-offs**: Distributed inference is 2-5 minutes slower to start and ~4x slower for inference compared to local. Use only when necessary.

### Overhead

- **Routing decision**: ~5-10ms (tested with 5-10 nodes)
- **Network overhead**: Varies by network (typically 5-20ms)
- **Total added latency**: ~20-50ms
- **Benefit**: Better resource utilization + automatic failover

---

## 🛠️ Advanced Configuration

### Custom Routing Strategy

```python
from sollol import OllamaPool

pool = OllamaPool(
    nodes=[
        {"host": "gpu-1.local", "port": 11434, "priority": 10},  # Prefer this
        {"host": "gpu-2.local", "port": 11434, "priority": 5},
        {"host": "cpu-1.local", "port": 11434, "priority": 1},   # Last resort
    ],
    enable_intelligent_routing=True,
    enable_hedging=True,  # Duplicate critical requests
    max_queue_size=100
)
```

### Priority-Based Scheduling

```python
# Critical user-facing request
response = pool.chat(
    model="llama3.2",
    messages=[...],
    priority=10  # Highest priority
)

# Background batch job
response = pool.chat(
    model="llama3.2",
    messages=[...],
    priority=1  # Lowest priority
)

# SOLLOL ensures high-priority requests jump the queue
```

### Observability & Monitoring

```python
# Get detailed stats
stats = pool.get_stats()
print(f"Total requests: {stats['total_requests']}")
print(f"Average latency: {stats['avg_latency_ms']}ms")
print(f"Success rate: {stats['success_rate']:.2%}")

# Per-node breakdown
for host, metrics in stats['hosts'].items():
    print(f"{host}: {metrics['latency_ms']}ms, {metrics['success_rate']:.2%}")
```

```bash
# Prometheus metrics endpoint
curl http://localhost:9090/metrics

# sollol_requests_total{host="gpu-1:11434",model="llama3.2"} 1234
# sollol_latency_seconds{host="gpu-1:11434"} 0.234
# sollol_success_rate{host="gpu-1:11434"} 0.98
```

---

## 🔌 Integration Examples

### SynapticLlamas Integration

```python
from sollol import SOLLOL, SOLLOLConfig
from synaptic_llamas import AgentOrchestrator

# Setup SOLLOL for multi-agent orchestration
config = SOLLOLConfig.auto_discover()
sollol = SOLLOL(config)
sollol.start(blocking=False)

# SynapticLlamas now uses SOLLOL for intelligent routing
orchestrator = AgentOrchestrator(
    llm_endpoint="http://localhost:8000/api/chat"
)

# All agents automatically distributed and optimized
orchestrator.run_parallel_agents([...])
```

### LangChain Integration

```python
from langchain.llms import Ollama
from sollol import OllamaPool

# Use SOLLOL as LangChain backend
pool = OllamaPool.auto_configure()

llm = Ollama(
    base_url="http://localhost:8000",
    model="llama3.2"
)

# LangChain requests now go through SOLLOL
response = llm("What is quantum computing?")
```

---

## 📚 Documentation

- **[Architecture Guide](ARCHITECTURE.md)** - Deep dive into system design
- **[llama.cpp Distributed Inference Guide](docs/llama_cpp_guide.md)** - Complete guide to model sharding
  - Setup and configuration
  - Performance optimization
  - Troubleshooting common issues
  - Advanced topics (custom layer distribution, monitoring, etc.)
- **[Integration Examples](examples/integration/)** - Practical integration patterns
  - [Synchronous Agent Integration](examples/integration/sync_agents.py)
  - [Priority Configuration](examples/integration/priority_mapping.py)
  - [Load Balancer Wrapper](examples/integration/load_balancer_wrapper.py)
- **[llama.cpp Distributed Examples](examples/llama_cpp_distributed.py)** - Model sharding examples
  - Auto-setup and manual configuration
  - Multi-turn conversations with monitoring
  - Batch processing with multiple models
  - Error handling and recovery patterns
- **[Deployment Guide](docs/deployment.md)** - Production deployment patterns
- **[API Reference](docs/api.md)** - Complete API documentation
- **[Performance Tuning](docs/performance.md)** - Optimization guide
- **[SynapticLlamas Learnings](SYNAPTICLLAMAS_LEARNINGS.md)** - Features from production use

---

## 🆕 What's New in v0.3.6

### Synchronous API
No more async/await required! SOLLOL now provides a synchronous API wrapper that works with traditional Python applications and agent frameworks.

```python
from sollol.sync_wrapper import OllamaPool, HybridRouter

pool = OllamaPool.auto_configure()  # No await needed
response = pool.chat(...)            # Synchronous call
```

### Priority Helpers
Semantic priority levels and role-based mapping make priority configuration much easier:

```python
from sollol.priority_helpers import Priority, get_priority_for_role

# Use semantic constants
priority = Priority.HIGH  # 7

# Or map from agent roles
priority = get_priority_for_role("researcher")  # 8
```

### SOLLOL Detection
Clients can now detect if SOLLOL is running vs native Ollama via:
- `X-Powered-By: SOLLOL` header on all responses
- `/api/health` endpoint returns `{"service": "SOLLOL", "version": "0.3.6"}`

### Integration Examples
Comprehensive examples showing:
- Synchronous agent integration patterns
- Priority configuration and mapping
- Wrapping SOLLOL around existing infrastructure
- Gradual migration from legacy systems

---

## 🆚 Comparison

### SOLLOL vs. Simple Load Balancers

| Feature | nginx/HAProxy | SOLLOL |
|---------|--------------|---------|
| Routing | Round-robin/random | Context-aware, adapts from history |
| Resource awareness | None | GPU/CPU/memory-aware |
| Failover | Manual config | Automatic detection & recovery |
| Model sharding | ❌ | ✅ llama.cpp integration |
| Task prioritization | ❌ | ✅ Priority queue |
| Observability | Basic | Rich metrics + dashboard |
| Setup | Complex config | Auto-discover |

### SOLLOL vs. Kubernetes

| Feature | Kubernetes | SOLLOL |
|---------|-----------|---------|
| **Complexity** | High - requires cluster setup | Low - pip install |
| **AI-specific** | Generic container orchestration | Purpose-built for LLMs |
| **Intelligence** | None | Task-aware routing |
| **Model sharding** | Manual | Automatic |
| **Best for** | Large-scale production | AI-focused teams |

**Use both!** Deploy SOLLOL on Kubernetes for ultimate scalability.

---

## 🤝 Contributing

We welcome contributions! Areas we'd love help with:

- ML-based routing predictions
- Additional monitoring integrations
- Cloud provider integrations
- Performance optimizations
- Documentation improvements

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

Created by [BenevolentJoker-JohnL](https://github.com/BenevolentJoker-JohnL)

Part of the [SynapticLlamas](https://github.com/BenevolentJoker-JohnL/SynapticLlamas) ecosystem.

Built with: Ray, Dask, FastAPI, llama.cpp, Ollama

---

## 🎯 What Makes SOLLOL Different?

1. **Combines task distribution AND model sharding** in one system
2. **Context-aware routing** that adapts based on performance metrics
3. **Auto-discovery** of nodes with minimal configuration
4. **Built-in failover** and priority queuing
5. **Purpose-built for Ollama clusters** (understands GPU requirements, task types)

**Limitations to know**:
- Model sharding verified with 13B models; larger models not extensively tested
- Performance benefits depend on network latency and workload patterns
- Not a drop-in replacement for single-node setups in all scenarios

---

<div align="center">

**Stop manually managing your LLM cluster. Let SOLLOL optimize it for you.**

[Get Started](#quick-start) • [View on GitHub](https://github.com/BenevolentJoker-JohnL/SOLLOL) • [Report Issue](https://github.com/BenevolentJoker-JohnL/SOLLOL/issues)

</div>
