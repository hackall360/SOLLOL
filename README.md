# SOLLOL - Production-Ready Orchestration for Local LLM Clusters

<div align="center">

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml/badge.svg)](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/BenevolentJoker-JohnL/SOLLOL/branch/main/graph/badge.svg)](https://codecov.io/gh/BenevolentJoker-JohnL/SOLLOL)
[![Ollama](https://img.shields.io/badge/Ollama-Compatible-green.svg)](https://ollama.ai/)
[![llama.cpp](https://img.shields.io/badge/llama.cpp-Integrated-orange.svg)](https://github.com/ggerganov/llama.cpp)

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

### 4. **Unified Observability for Your Entire AI Network**

SOLLOL provides a **single pane of glass** to monitor every application and every node in your distributed AI network.

- ✅ **Centralized Dashboard**: One web interface shows all applications, nodes, and RPC backends.
- ✅ **Multi-App Tracking**: See which applications (e.g., SynapticLlamas, custom agents) are using the cluster in real-time.
- ✅ **Network-Wide Visibility**: The dashboard runs as a persistent service, discovering and monitoring all components even if no applications are running.
- ✅ **Zero-Config**: Applications automatically appear in the dashboard with no extra code required.

This moves beyond per-application monitoring to provide true, centralized observability for your entire infrastructure.

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

#### RPC Server Auto-Installation

**SOLLOL can automatically clone, build, and start llama.cpp RPC servers for you!**

**One-line installation:**

```python
from sollol.rpc_auto_setup import auto_setup_rpc_backends

# Automatically: clone → build → start RPC servers
backends = auto_setup_rpc_backends(num_backends=2)
# Output: [{'host': '127.0.0.1', 'port': 50052}, {'host': '127.0.0.1', 'port': 50053}]
```

**What this does:**
1. ✅ Scans network for existing RPC servers
2. ✅ If none found: clones llama.cpp to `~/llama.cpp`
3. ✅ Builds llama.cpp with RPC support (`cmake -DGGML_RPC=ON`)
4. ✅ Starts RPC servers on ports 50052-50053
5. ✅ Returns ready-to-use backend list

**CLI installation:**

```bash
# Full automated setup (clone + build + install systemd service)
python3 -m sollol.setup_llama_cpp --all

# Or step by step
python3 -m sollol.setup_llama_cpp --clone  # Clone llama.cpp
python3 -m sollol.setup_llama_cpp --build  # Build with RPC support
python3 -m sollol.setup_llama_cpp --start  # Start RPC server
```

**Docker IP Resolution:**

SOLLOL automatically resolves Docker container IPs to accessible host IPs:

```python
# If Docker container reports IP 172.17.0.5:11434
# SOLLOL automatically resolves to:
# → 127.0.0.1:11434 (published port mapping)
# → host IP (if accessible)
# → Docker host gateway

from sollol import is_docker_ip, resolve_docker_ip

# Check if IP is Docker internal
is_docker = is_docker_ip("172.17.0.5")  # True

# Resolve Docker IP to accessible IP
accessible_ip = resolve_docker_ip("172.17.0.5", port=11434)
# Returns: "127.0.0.1" or host IP
```

**Network Discovery with Docker Support:**

```python
from sollol import OllamaPool

# Auto-discover nodes (automatically resolves Docker IPs)
pool = OllamaPool.auto_configure()

# Manual control
from sollol.discovery import discover_ollama_nodes
nodes = discover_ollama_nodes(auto_resolve_docker=True)
```

**Multi-Node Production Setup:**

For distributed clusters, use systemd services on each node:

```bash
# On each RPC node
sudo systemctl enable llama-rpc@50052.service
sudo systemctl start llama-rpc@50052.service
```

See [SOLLOL_RPC_SETUP.md](https://github.com/BenevolentJoker-JohnL/FlockParser/blob/main/SOLLOL_RPC_SETUP.md) for complete installation guide.

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

---

### 5. Batch Processing API

**New in v0.7.0:** RESTful API for asynchronous batch job management.

Submit large-scale batch operations (thousands of embeddings, bulk inference) and track progress via job IDs:

```python
import requests

# Submit batch embedding job (up to 10,000 documents)
response = requests.post("http://localhost:11434/api/batch/embed", json={
    "model": "nomic-embed-text",
    "documents": ["Document 1", "Document 2", ...],  # Can be thousands
    "metadata": {"source": "knowledge_base"}  # Optional metadata
})

job_id = response.json()["job_id"]
print(f"Job submitted: {job_id}")

# Poll for job status
import time
while True:
    status = requests.get(f"http://localhost:11434/api/batch/jobs/{job_id}").json()

    progress = status["progress"]["percent"]
    print(f"Progress: {progress}%")

    if status["status"] == "completed":
        break
    time.sleep(1)

# Get results
results = requests.get(f"http://localhost:11434/api/batch/results/{job_id}").json()
embeddings = results["results"]  # List of embedding vectors
print(f"Processed {len(embeddings)} documents in {status['duration_seconds']}s")
```

**Available Batch Endpoints:**
- `POST /api/batch/embed` - Submit batch embedding job
- `GET /api/batch/jobs/{job_id}` - Get job status
- `GET /api/batch/results/{job_id}` - Get job results
- `GET /api/batch/jobs?limit=100` - List recent jobs
- `DELETE /api/batch/jobs/{job_id}` - Cancel job

**Use cases:**
- Embedding large document collections (thousands of documents)
- Bulk inference for batch predictions
- Background processing without blocking
- Long-running operations with progress tracking

---

### 6. SOLLOL Detection

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

### 7. Production Gateway

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

#### **Zero-Config Auto-Registration** 🎯

SOLLOL provides **automatic observability** with zero configuration required. All applications automatically register with the dashboard when they create an `OllamaPool`:

```python
from sollol import OllamaPool

# Creates pool AND auto-registers with dashboard (if running)
pool = OllamaPool.auto_configure()
# ✅ Application automatically appears in dashboard at http://localhost:8080
```

**How it works:**
1. `OllamaPool` automatically detects if a dashboard is running on port 8080
2. Auto-discovers RPC backends and Ollama nodes
3. Registers application with metadata (node count, GPU info, etc.)
4. Sends periodic heartbeats to maintain "alive" status
5. No manual `DashboardClient` setup needed!

**Architecture:**
- **ONE persistent dashboard service** runs independently
- **Multiple applications** (SynapticLlamas, FlockParser, etc.) auto-register
- **Dashboard survives** application exits
- **Zero-config** auto-discovery of nodes and RPC backends

#### **Custom Application Names** 🏷️

By default, applications register as "OllamaPool (hostname)". To give your application a custom name in the dashboard:

```python
from sollol import OllamaPool

# Register with custom application name
pool = OllamaPool(
    nodes=[{"host": "localhost", "port": 11434}],
    enable_intelligent_routing=True,
    app_name="MyApplication"  # Shows as "MyApplication" in dashboard
)
```

**Example - Multi-application setup:**

```python
# Application 1: FlockParser
from sollol import OllamaPool

pool = OllamaPool.auto_configure(app_name="FlockParser")
# Dashboard shows: "FlockParser"

# Application 2: SynapticLlamas
from sollol.dashboard_client import DashboardClient

dashboard_client = DashboardClient(
    app_name="SynapticLlamas",
    router_type="IntelligentRouter",
    version="1.0.0",
    dashboard_url="http://localhost:8080",
    metadata={"agents": 3, "distributed": True},
    auto_register=True
)
# Dashboard shows: "SynapticLlamas"
```

**Why use custom names?**
- Distinguish between multiple applications using SOLLOL
- Better visibility in multi-tenant environments
- Easier debugging and monitoring
- Professional dashboard presentation

#### **Manual/Programmatic Registration** 🔧

For applications that don't use `OllamaPool` or need custom registration logic, use `DashboardClient` directly:

```python
from sollol.dashboard_client import DashboardClient

# Create dashboard client with custom metadata
dashboard_client = DashboardClient(
    app_name="CustomApplication",
    router_type="CustomRouter",  # Or "OllamaPool", "HybridRouter", etc.
    version="1.0.0",
    dashboard_url="http://localhost:8080",
    metadata={
        # Custom metadata shown in dashboard
        "nodes": 5,
        "distributed": True,
        "custom_field": "value"
    },
    auto_register=True  # Registers immediately
)

# Dashboard client automatically sends heartbeats every 5 seconds
# to keep application status as "active"

# When application exits, clean up:
dashboard_client.close()  # Stops heartbeat thread
```

**Advanced: Custom Heartbeat Logic**

```python
from sollol.dashboard_client import DashboardClient
import time

# Create client without auto-registration
dashboard_client = DashboardClient(
    app_name="BackgroundWorker",
    router_type="WorkerPool",
    version="2.0.0",
    dashboard_url="http://localhost:8080",
    metadata={"worker_count": 10},
    auto_register=False  # Don't register yet
)

# Register when ready
dashboard_client.register()

# Update metadata dynamically
dashboard_client.update_metadata({"worker_count": 15, "status": "processing"})

# Send manual heartbeat
dashboard_client.heartbeat()

# Application logic here...
time.sleep(60)

# Deregister when done
dashboard_client.deregister()
dashboard_client.close()
```

**Use cases for manual registration:**
- Custom routers or load balancers
- Background workers or daemons
- Applications that need dynamic metadata updates
- Testing and debugging
- Applications without OllamaPool

#### **Registration Methods Comparison** 📊

| Method | Use Case | Complexity | Customization |
|--------|----------|------------|---------------|
| **Auto-registration** | Standard SOLLOL applications | ✅ Zero config | Limited (app_name only) |
| **Custom app_name** | Multiple apps, better naming | ✅ One parameter | App name |
| **Manual DashboardClient** | Custom applications | ⚠️ More code | Full control |

**Quick decision guide:**
- Using `OllamaPool`? → Use `app_name` parameter
- Need custom metadata? → Use `DashboardClient` directly
- Need dynamic updates? → Use `DashboardClient` with manual heartbeats
- Just want it to work? → Use auto-registration (default)

#### **Persistent Dashboard Service**

Start the persistent dashboard once (survives application exits):

```bash
# Start dashboard service (runs until stopped)
python3 -m sollol.dashboard_service --port 8080 --redis-url redis://localhost:6379

# Or run in background
nohup python3 -m sollol.dashboard_service --port 8080 --redis-url redis://localhost:6379 > /tmp/dashboard_service.log 2>&1 &
```

**Features:**
- 📊 **Real-time metrics**: System status, latency, success rate, GPU memory, Ray workers
- 📜 **Live log streaming**: WebSocket-based log tailing (via Redis pub/sub)
- 🌐 **Activity monitoring**: Ollama server and llama.cpp RPC activity
- 🔷 **Embedded Ray dashboard**: Task-level distributed tracing
- 📈 **Embedded Dask dashboard**: Performance profiling and task graphs
- 🔍 **Auto-discovery**: Automatically discovers Ollama nodes and RPC backends when no router context

#### **Embedded Dashboard (Alternative)**

Applications can also start their own embedded dashboards:

```python
from sollol import run_unified_dashboard
import threading

# Start embedded dashboard with router context
dashboard_thread = threading.Thread(
    target=run_unified_dashboard,
    kwargs={
        "router": pool,  # Provides node/backend context
        "dashboard_port": 8080,
        "host": "0.0.0.0",
        "enable_dask": False
    },
    daemon=True
)
dashboard_thread.start()
```

**Environment Variables** (configure before initializing):

```bash
# Disable dashboard (default: true)
export SOLLOL_DASHBOARD=false

# Change dashboard port (default: 8080)
export SOLLOL_DASHBOARD_PORT=9090

# Disable Dask dashboard integration (default: true)
export SOLLOL_DASHBOARD_DASK=false
```

#### **Multi-Application Pattern** ✨

The persistent dashboard service enables multiple applications to share observability:

```bash
# Terminal 1: Start persistent dashboard
python3 -m sollol.dashboard_service --port 8080 --redis-url redis://localhost:6379

# Terminal 2: Start application 1
python my_app1.py  # Auto-registers with dashboard

# Terminal 3: Start application 2
python my_app2.py  # Also auto-registers

# Visit http://localhost:8080 to see both applications!
```

**Benefits:**
- Single dashboard for all SOLLOL-based applications
- Dashboard stays running when applications exit
- Aggregated logs from all applications (via Redis pub/sub)
- Centralized observability for distributed systems

#### **Programmatic Stats Access**

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

#### **Prometheus Metrics**

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
- **[Backend Architecture](BACKENDS.md)** - Backend extensibility and adding new LLM backends
- **[Batch Processing API](BATCH_API.md)** - Complete guide to batch job management (NEW in v0.7.0)
  - API endpoints and examples
  - Job lifecycle and progress tracking
  - Best practices and error handling
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

## 🆕 What's New in v0.7.0

### 📦 Batch Processing API
Complete RESTful API for asynchronous batch job management. Submit large-scale batch operations (embeddings, bulk inference) and track progress via job IDs.

```python
import requests

# Submit batch embedding job (up to 10,000 documents)
response = requests.post("http://localhost:11434/api/batch/embed", json={
    "model": "nomic-embed-text",
    "documents": ["doc1", "doc2", ...],  # Thousands of documents
})
job_id = response.json()["job_id"]

# Check status
status = requests.get(f"http://localhost:11434/api/batch/jobs/{job_id}")
print(status.json()["progress"]["percent"])  # 100.0

# Get results
results = requests.get(f"http://localhost:11434/api/batch/results/{job_id}")
embeddings = results.json()["results"]
```

**Batch API Endpoints:**
- `POST /api/batch/embed` - Submit batch embedding job
- `GET /api/batch/jobs/{job_id}` - Get job status with progress tracking
- `GET /api/batch/results/{job_id}` - Retrieve job results and errors
- `DELETE /api/batch/jobs/{job_id}` - Cancel running jobs
- `GET /api/batch/jobs?limit=100` - List recent jobs

**Features:**
- UUID-based job tracking with 5 states (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- Automatic TTL-based cleanup (1 hour default)
- Progress tracking: completed_items, failed_items, percentage
- Duration calculation and metadata storage
- Async job execution via Dask distributed processing

### Previous Features (v0.3.6+)

**Synchronous API** - No async/await required:
```python
from sollol.sync_wrapper import OllamaPool
pool = OllamaPool.auto_configure()
response = pool.chat(...)  # Synchronous call
```

**Priority Helpers** - Semantic priority levels:
```python
from sollol.priority_helpers import Priority
priority = Priority.HIGH  # 7
```

**SOLLOL Detection:**
- `X-Powered-By: SOLLOL` header on all responses
- `/api/health` endpoint returns `{"service": "SOLLOL", "version": "0.7.0"}`

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
