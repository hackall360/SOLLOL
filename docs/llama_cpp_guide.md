# llama.cpp Model Sharding Guide

**Complete guide to running large language models across multiple machines using SOLLOL's llama.cpp integration.**

---

## Table of Contents

1. [Overview](#overview)
2. [What is Model Sharding?](#what-is-model-sharding)
3. [Architecture](#architecture)
4. [When to Use Model Sharding](#when-to-use-model-sharding)
5. [Setup Guide](#setup-guide)
6. [Usage Examples](#usage-examples)
7. [Model Profiles](#model-profiles)
8. [Performance & Optimization](#performance--optimization)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Topics](#advanced-topics)

---

## Overview

SOLLOL integrates with [llama.cpp](https://github.com/ggerganov/llama.cpp) to enable **model sharding** - the ability to run models that are too large to fit on a single GPU by distributing them across multiple machines.

### Key Benefits

- ✅ **Run 70B+ models** on machines with limited VRAM
- ✅ **Automatic GGUF extraction** from Ollama storage
- ✅ **Zero-config setup** with auto-discovery
- ✅ **Seamless integration** with SOLLOL's intelligent routing
- ✅ **Hybrid operation** - small models use Ollama, large models use sharding

### What You Get

```python
from sollol.sync_wrapper import HybridRouter, OllamaPool

# Auto-configure with model sharding enabled
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    num_rpc_backends=3  # Shard across 3 machines
)

# Small models → Ollama (fast, local)
response = router.route_request(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Large models → llama.cpp sharding (distributed)
response = router.route_request(
    model="llama3.1:70b",
    messages=[{"role": "user", "content": "Complex task..."}]
)
```

---

## What is Model Sharding?

### The Problem

Large language models like Llama 3.1 70B require ~40GB of VRAM. If you only have GPUs with 24GB VRAM, you can't run these models locally.

**Traditional options:**
- ❌ Cloud APIs (expensive, privacy concerns)
- ❌ Upgrade to more expensive hardware
- ❌ Use smaller, less capable models

### The Solution: Model Sharding

**Model sharding** distributes a single model across multiple machines:

```
┌─────────────────────────────────────────────────┐
│         Llama 3.1 70B Model (40GB total)        │
└─────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Machine 1  │ │   Machine 2  │ │   Machine 3  │
│              │ │              │ │              │
│ Layers 0-26  │ │ Layers 27-53 │ │ Layers 54-79 │
│   (~13GB)    │ │   (~13GB)    │ │   (~13GB)    │
│              │ │              │ │              │
│ RTX 4090     │ │ RTX 4090     │ │ RTX 4090     │
│  24GB VRAM   │ │  24GB VRAM   │ │  24GB VRAM   │
└──────────────┘ └──────────────┘ └──────────────┘
```

**How it works:**
1. Model layers are split across machines
2. During inference, data flows through each machine sequentially
3. llama.cpp RPC (Remote Procedure Call) handles communication
4. SOLLOL coordinates everything automatically

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      SOLLOL Gateway                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              HybridRouter                            │  │
│  │  • Analyzes model requirements                       │  │
│  │  • Routes small models → Ollama                      │  │
│  │  │  • Routes large models → llama.cpp coordinator    │  │
│  └──────────────┬───────────────────────────────────────┘  │
└─────────────────┼──────────────────────────────────────────┘
                  │
     ┌────────────┴────────────┐
     │                         │
     ▼                         ▼
┌─────────────┐       ┌──────────────────────────────────────┐
│   Ollama    │       │   llama.cpp Coordinator              │
│   Nodes     │       │   (llama-server)                     │
│             │       │                                      │
│ • llama3.2  │       │   • Loads GGUF model                 │
│ • phi       │       │   • Distributes layers to RPC nodes  │
│ • codellama │       │   • Coordinates inference            │
│             │       │   • Returns results to SOLLOL        │
│  (Fast,     │       └────────────┬─────────────────────────┘
│   local)    │                    │
└─────────────┘         ┌──────────┴──────────┬──────────────┐
                        │                     │              │
                        ▼                     ▼              ▼
                  ┌──────────┐          ┌──────────┐  ┌──────────┐
                  │ RPC Node │          │ RPC Node │  │ RPC Node │
                  │    #1    │          │    #2    │  │    #3    │
                  │          │          │          │  │          │
                  │ Layers   │          │ Layers   │  │ Layers   │
                  │  0-26    │          │  27-53   │  │  54-79   │
                  └──────────┘          └──────────┘  └──────────┘
```

### Key Components Explained

**1. HybridRouter**
- Analyzes incoming requests
- Determines if model needs sharding
- Routes to appropriate backend

**2. llama.cpp Coordinator (llama-server)**
- Central control process
- Loads the GGUF model file
- Distributes layers to RPC backends
- Coordinates inference passes

**3. RPC Backends (rpc-server)**
- Worker processes on each machine
- Execute inference for assigned layers
- Communicate via gRPC

**4. GGUF Extraction**
- SOLLOL automatically finds GGUFs in Ollama storage
- No manual file management needed

---

## When to Use Model Sharding

### Use Model Sharding When:

✅ **Model is too large for single GPU**
- Llama 3.1 70B (~40GB) on 24GB GPUs
- Mixtral 8x7B (~26GB) on 16GB GPUs
- Any model > available VRAM

✅ **You have multiple machines with GPUs**
- 2-4 machines with GPUs
- Network connection between them
- Want to utilize distributed resources

✅ **Throughput is acceptable**
- Understand ~2-5x slower than local inference
- Startup time (2-5 minutes) is acceptable
- Network latency is reasonable (<10ms)

### Don't Use Model Sharding When:

❌ **Model fits on single GPU**
- Use Ollama directly (much faster)
- Example: Llama 3.2 3B, Phi-3, CodeLlama 7B

❌ **Need lowest latency**
- Model sharding adds network overhead
- Better: Use smaller model or upgrade hardware

❌ **Poor network connectivity**
- High latency (>50ms) kills performance
- RPC requires fast, reliable network

---

## Setup Guide

### Prerequisites

**Hardware:**
- 2+ machines with GPUs (or CPUs for testing)
- Network connectivity between machines
- Sufficient VRAM across machines for model

**Software:**
- Python 3.8+
- Ollama installed (for GGUF extraction)
- CMake (for building llama.cpp)
- Git

### Option 1: Auto-Setup (Recommended)

SOLLOL can automatically setup llama.cpp RPC backends:

```python
from sollol.sync_wrapper import HybridRouter, OllamaPool

# Auto-setup everything
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    auto_discover_rpc=True,    # Try to find existing RPC servers
    auto_setup_rpc=True,        # Build/start RPC if not found
    num_rpc_backends=3          # Number of RPC servers to start
)

# SOLLOL will:
# 1. Look for running RPC servers on the network
# 2. If not found, clone llama.cpp repository
# 3. Build llama.cpp with RPC support
# 4. Start RPC servers on available ports
# 5. Configure HybridRouter to use them
```

**What auto-setup does:**
1. Checks for `llama.cpp` directory in `~/llama.cpp`
2. If not found, clones from GitHub
3. Builds with `cmake -DGGML_RPC=ON`
4. Starts `rpc-server` processes on ports 50052, 50053, etc.
5. Configures coordinator to use these backends

### Option 2: Manual Setup

For more control, setup llama.cpp manually:

**Step 1: Install llama.cpp**

```bash
# Clone llama.cpp
cd ~
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build with RPC support
cmake -B build -DGGML_RPC=ON -DLLAMA_CURL=OFF
cmake --build build --config Release -j$(nproc)
```

**Step 2: Start RPC Servers**

On each machine that will participate in sharding:

```bash
# Machine 1
~/llama.cpp/build/bin/rpc-server -H 0.0.0.0 -p 50052

# Machine 2
~/llama.cpp/build/bin/rpc-server -H 0.0.0.0 -p 50052

# Machine 3
~/llama.cpp/build/bin/rpc-server -H 0.0.0.0 -p 50052
```

**Step 3: Configure SOLLOL**

```python
from sollol.sync_wrapper import HybridRouter, OllamaPool

# Manual RPC backend configuration
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    rpc_backends=[
        {"host": "192.168.1.10", "port": 50052},
        {"host": "192.168.1.11", "port": 50052},
        {"host": "192.168.1.12", "port": 50052},
    ]
)
```

### Option 3: Using Environment Variables

```bash
# Set RPC backends via environment
export RPC_BACKENDS="192.168.1.10:50052,192.168.1.11:50052,192.168.1.12:50052"

# Run SOLLOL gateway
python -m sollol.gateway
```

```python
# HybridRouter will pick up RPC_BACKENDS automatically
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True
)
```

### Verification

Check that RPC backends are accessible:

```bash
# Test RPC connectivity
nc -zv 192.168.1.10 50052
nc -zv 192.168.1.11 50052
nc -zv 192.168.1.12 50052
```

```python
# Verify in Python
from sollol.rpc_discovery import test_rpc_backend

result = test_rpc_backend("192.168.1.10", 50052)
print(f"RPC backend: {'✓ Available' if result else '✗ Not available'}")
```

---

## Usage Examples

### Example 1: Basic Model Sharding

```python
from sollol.sync_wrapper import HybridRouter, OllamaPool
from sollol.priority_helpers import Priority

# Setup router with model sharding
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    num_rpc_backends=3
)

# Small model - uses Ollama (fast)
print("Running small model...")
response = router.route_request(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}],
    priority=Priority.HIGH
)
print(f"Backend: {response.get('_routing', {}).get('backend')}")
# Output: Backend: ollama-pool

# Large model - uses llama.cpp sharding (distributed)
print("\nRunning large model...")
response = router.route_request(
    model="llama3.1:70b",
    messages=[{"role": "user", "content": "Explain quantum computing"}],
    priority=Priority.NORMAL
)
print(f"Backend: {response.get('_routing', {}).get('backend')}")
# Output: Backend: llama.cpp-distributed
```

### Example 2: Check Model Routing Decision

```python
# Check which backend will be used before making request
model = "llama3.1:70b"
will_use_sharding = router.should_use_distributed(model)

if will_use_sharding:
    print(f"{model} will use distributed inference (llama.cpp)")
    print("Expected: Slower startup, network overhead")
else:
    print(f"{model} will use local Ollama")
    print("Expected: Fast, low latency")
```

### Example 3: Monitor Coordinator Status

```python
# Get coordinator information
if router.coordinator:
    print(f"Coordinator running: {router.coordinator.is_running()}")
    print(f"Coordinator model: {router.coordinator_model}")
    print(f"RPC backends: {len(router.coordinator.rpc_backends)}")
    print(f"Coordinator URL: {router.coordinator.base_url}")
else:
    print("No coordinator active (using Ollama only)")
```

### Example 4: Async Usage

```python
import asyncio
from sollol import HybridRouter, OllamaPool

async def run_distributed_inference():
    # Create router (async version)
    pool = await OllamaPool.auto_configure()
    router = HybridRouter(
        ollama_pool=pool,
        enable_distributed=True,
        num_rpc_backends=3
    )

    # Run inference
    response = await router.route_request(
        model="llama3.1:70b",
        messages=[{"role": "user", "content": "What is AGI?"}]
    )

    print(response['message']['content'])

asyncio.run(run_distributed_inference())
```

### Example 5: Multi-Agent with Mixed Models

```python
from sollol.sync_wrapper import HybridRouter, OllamaPool
from sollol.priority_helpers import get_priority_for_role

router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    num_rpc_backends=3
)

agents = [
    {"name": "Researcher", "role": "researcher", "model": "llama3.1:70b"},  # Sharded
    {"name": "Editor", "role": "editor", "model": "llama3.2"},              # Local
    {"name": "Summarizer", "role": "summarizer", "model": "llama3.2"},      # Local
]

for agent in agents:
    priority = get_priority_for_role(agent["role"])

    response = router.route_request(
        model=agent["model"],
        messages=[{"role": "user", "content": f"Task for {agent['name']}"}],
        priority=priority
    )

    backend = response.get('_routing', {}).get('backend', 'unknown')
    print(f"{agent['name']} ({agent['model']}): {backend}")
```

---

## Model Profiles

SOLLOL uses model profiles to automatically determine routing strategy:

### Built-in Profiles

```python
MODEL_PROFILES = {
    # Small models - Ollama
    "llama3.2": {
        "parameter_count": 3,
        "estimated_memory_gb": 2,
        "requires_distributed": False
    },
    "phi": {
        "parameter_count": 3,
        "estimated_memory_gb": 1.5,
        "requires_distributed": False
    },

    # Medium models - Ollama (if fits)
    "llama3.1:8b": {
        "parameter_count": 8,
        "estimated_memory_gb": 5,
        "requires_distributed": False
    },
    "codellama:13b": {
        "parameter_count": 13,
        "estimated_memory_gb": 8,
        "requires_distributed": False
    },

    # Large models - llama.cpp sharding
    "llama3.1:70b": {
        "parameter_count": 70,
        "estimated_memory_gb": 40,
        "requires_distributed": True
    },
    "llama3.1:405b": {
        "parameter_count": 405,
        "estimated_memory_gb": 240,
        "requires_distributed": True
    },
    "mixtral:8x7b": {
        "parameter_count": 47,  # MoE model
        "estimated_memory_gb": 26,
        "requires_distributed": True
    }
}
```

### Custom Model Profiles

Add your own model profiles:

```python
from sollol.hybrid_router import MODEL_PROFILES

# Add custom model
MODEL_PROFILES["custom-70b"] = {
    "parameter_count": 70,
    "estimated_memory_gb": 42,
    "requires_distributed": True
}

# Now SOLLOL will route it to llama.cpp automatically
router.route_request(
    model="custom-70b",
    messages=[...]
)
```

### Threshold Configuration

Adjust when sharding is used:

```python
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    distributed_threshold_params=30,  # Shard models > 30B parameters
    num_rpc_backends=3
)
```

---

## Performance & Optimization

### Performance Characteristics

**Startup Time:**
- First request: 2-5 minutes (model loading + layer distribution)
- Subsequent requests: <1 second (coordinator reuse)

**Inference Speed:**
- Local Ollama: ~20-40 tokens/sec (single GPU)
- 2-node sharding: ~5-10 tokens/sec (~3-4× slower)
- 3-node sharding: ~3-7 tokens/sec (~5-6× slower)

**Network Impact:**
```
Latency Impact:
- <1ms: Excellent (local network)
- 1-10ms: Good (same datacenter)
- 10-50ms: Acceptable (same region)
- >50ms: Poor (cross-region)
```

### Optimization Tips

**1. Minimize RPC Hops**
```python
# Good: 2-3 backends (fewer network hops)
router = HybridRouter(num_rpc_backends=2)

# Avoid: 5+ backends (too many hops)
router = HybridRouter(num_rpc_backends=6)
```

**2. Use Fast Network**
```bash
# Check network latency between machines
ping -c 10 192.168.1.11

# Ensure <10ms latency for good performance
```

**3. Optimize Context Size**
```python
# Smaller context = faster inference
response = router.route_request(
    model="llama3.1:70b",
    messages=[...],
    max_tokens=512  # Limit response length
)
```

**4. Coordinator Reuse**
```python
# Coordinator stays loaded between requests
# Subsequent requests are much faster

# First request: 2-5 min (startup + inference)
response1 = router.route_request(model="llama3.1:70b", messages=[...])

# Second request: <1 min (inference only)
response2 = router.route_request(model="llama3.1:70b", messages=[...])
```

**5. Monitor Performance**
```python
response = router.route_request(
    model="llama3.1:70b",
    messages=[...]
)

# Check routing metadata
routing = response.get('_routing', {})
print(f"Backend: {routing.get('backend')}")
print(f"Duration: {routing.get('duration_ms')}ms")
print(f"Coordinator: {routing.get('coordinator_url')}")
```

---

## Troubleshooting

### Issue: RPC Backends Not Found

**Symptoms:**
```
⚠️  No RPC backends found
📡 Model sharding disabled
```

**Solutions:**

1. **Check RPC servers are running:**
```bash
# List running RPC servers
ps aux | grep rpc-server

# Should show:
# ./build/bin/rpc-server -H 0.0.0.0 -p 50052
```

2. **Verify network connectivity:**
```bash
# Test port accessibility
nc -zv 192.168.1.10 50052

# Check firewall
sudo ufw allow 50052
```

3. **Enable auto-setup:**
```python
router = HybridRouter(
    enable_distributed=True,
    auto_setup_rpc=True,  # Let SOLLOL build/start RPC servers
    num_rpc_backends=3
)
```

### Issue: Coordinator Startup Timeout

**Symptoms:**
```
🚀 Starting llama.cpp coordinator...
[waits 20+ minutes]
TimeoutError: Coordinator failed to start
```

**Solutions:**

1. **Increase timeout:**
```python
router = HybridRouter(
    enable_distributed=True,
    coordinator_timeout=1200,  # 20 minutes for 70B models
    num_rpc_backends=3
)
```

2. **Check logs:**
```bash
# View llama-server output
tail -f /tmp/llama_coordinator_*.log
```

3. **Verify GGUF exists:**
```python
from sollol.ollama_gguf_resolver import OllamaGGUFResolver

resolver = OllamaGGUFResolver()
gguf_path = resolver.get_gguf_path("llama3.1:70b")
print(f"GGUF: {gguf_path}")

# Should print path like:
# /usr/share/ollama/.ollama/models/blobs/sha256-abc123...
```

### Issue: Inference Timeout

**Symptoms:**
```
✅ Coordinator started successfully
[inference request sent]
[waits 5+ minutes]
TimeoutError: Request timeout after 300s
```

**Solutions:**

1. **Increase request timeout:**
```python
response = router.route_request(
    model="llama3.1:70b",
    messages=[...],
    timeout=600  # 10 minutes
)
```

2. **Check coordinator is responding:**
```bash
# Test coordinator health
curl http://localhost:18080/health
```

3. **Verify RPC communication:**
```bash
# Check RPC backend logs
# Look for layer assignment messages
```

### Issue: Coordinator Crashes After First Request

**Symptoms:**
```
✅ First inference successful
[second request]
🚀 Starting llama.cpp coordinator... (again)
```

**Solutions:**

1. **Check process liveness:**
```python
# SOLLOL should detect dead processes
# Look for: "⚠️  Coordinator process died!"
```

2. **Increase coordinator memory:**
```bash
# Give coordinator more memory
export LLAMA_ARG_N_GPU_LAYERS=40
```

3. **Check for OOM kills:**
```bash
# Check system logs
dmesg | grep -i "out of memory"
journalctl -xe | grep llama
```

### Issue: Slow Performance

**Symptoms:**
- Inference takes 30+ seconds per token
- Network appears saturated

**Solutions:**

1. **Reduce number of backends:**
```python
# Fewer backends = fewer network hops
router = HybridRouter(num_rpc_backends=2)  # Instead of 4
```

2. **Check network latency:**
```bash
ping -c 100 192.168.1.11
# Should be <10ms average
```

3. **Use local network:**
```bash
# Ensure all machines are on same LAN
# Avoid VPN or WAN connections
```

---

## Advanced Topics

### Custom GGUF Paths

Override automatic GGUF detection:

```python
from sollol import HybridRouter, OllamaPool

router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    gguf_path="/path/to/custom/model.gguf"
)
```

### Multiple Coordinators

Run different models simultaneously:

```python
# Not currently supported - coordinators are per-HybridRouter
# Workaround: Use separate HybridRouter instances

router_70b = HybridRouter(
    enable_distributed=True,
    model_filter=["llama3.1:70b"]
)

router_405b = HybridRouter(
    enable_distributed=True,
    model_filter=["llama3.1:405b"]
)
```

### Layer Distribution Strategies

Coming soon: Custom layer distribution

```python
# Future feature
router = HybridRouter(
    enable_distributed=True,
    layer_strategy="memory_aware",  # Distribute based on VRAM
    # or "even" for equal distribution
)
```

### Monitoring & Metrics

Get detailed metrics:

```python
stats = router.get_stats()

print(f"Distributed requests: {stats.get('distributed_requests', 0)}")
print(f"Coordinator uptime: {stats.get('coordinator_uptime_seconds', 0)}s")
print(f"Active RPC backends: {stats.get('active_rpc_backends', 0)}")
```

---

## See Also

- [ARCHITECTURE.md](../ARCHITECTURE.md) - SOLLOL architecture overview
- [HybridRouter API](../README.md#hybridrouter) - HybridRouter documentation
- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp) - llama.cpp project
- [Integration Examples](../examples/integration/) - More usage examples

---

## Summary

**SOLLOL's llama.cpp integration makes model sharding accessible:**

✅ **Easy Setup** - Auto-discovery and auto-setup
✅ **Intelligent Routing** - Automatic backend selection
✅ **GGUF Extraction** - No manual file management
✅ **Hybrid Operation** - Small models stay fast, large models become possible
✅ **Production Ready** - Coordinator reuse, health checking, failover

**Quick Start:**
```python
from sollol.sync_wrapper import HybridRouter, OllamaPool

router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    auto_setup_rpc=True,
    num_rpc_backends=3
)

# Just use it - SOLLOL handles the rest
response = router.route_request(
    model="llama3.1:70b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**That's it!** 🚀
