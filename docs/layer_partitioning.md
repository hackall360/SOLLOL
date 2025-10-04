# Layer Partitioning for Large Models

SOLLOL now supports **layer partitioning** - the ability to split large models (70B+) across multiple nodes for distributed inference.

## Overview

**What it does:**
- Splits models too large for a single GPU across multiple nodes
- Each node loads specific layers (e.g., node1: layers 0-39, node2: layers 40-79)
- Coordinates inference across nodes automatically
- Provides both vertical scaling (bigger models) and horizontal scaling (more throughput)

**When to use it:**
- Models larger than your single-node GPU memory (Llama-70B, Mixtral-8x7B, etc.)
- You have multiple GPUs across different machines
- You want to run models that wouldn't fit otherwise

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    SOLLOL Gateway                    │
│                                                      │
│  Request for llama2:70b                              │
│    ↓                                                 │
│  Routing Decision:                                   │
│    - Small model (llama3.2) → Individual node        │
│    - Large model (llama2:70b) → Cluster              │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────────┐         ┌──────────────────┐
│   Individual     │         │   Node Cluster   │
│      Node        │         │   (llama2:70b)   │
│                  │         │                  │
│  • llama3.2      │         │  Node 1:         │
│  • phi           │         │    Layers 0-39   │
│  • codellama     │         │                  │
│                  │         │  Node 2:         │
│  Full model      │         │    Layers 40-79  │
│  on single GPU   │         │                  │
└──────────────────┘         │  Distributed     │
                             │  inference       │
                             └──────────────────┘
```

## Quick Start

### 1. Add Nodes to Registry

```python
from sollol.registry import NodeRegistry

registry = NodeRegistry()

# Add individual nodes
registry.add_node("http://192.168.1.10:11434", name="gpu-node-1")
registry.add_node("http://192.168.1.11:11434", name="gpu-node-2")
registry.add_node("http://192.168.1.12:11434", name="gpu-node-3")
```

### 2. Create Cluster for Large Model

```python
# Create cluster for Llama-70B across 2 nodes
cluster = registry.create_cluster(
    name="llama70b-cluster",
    node_urls=[
        "http://192.168.1.10:11434",
        "http://192.168.1.11:11434"
    ],
    model="llama2:70b",
    partitioning_strategy="even"  # or "memory_aware"
)

# Output:
# 📦 Created cluster 'llama70b-cluster' with 2 nodes for llama2:70b
#    Node 1: layers 0-39 (40 layers)
#    Node 2: layers 40-79 (40 layers)
```

### 3. Use Smart Routing

```python
# Get best worker for model (automatically selects cluster for large models)
worker = registry.get_worker_for_model("llama2:70b")

if isinstance(worker, NodeCluster):
    print(f"Using cluster: {worker.name}")
    result = await worker.generate("Explain quantum computing")
else:
    print(f"Using single node: {worker.name}")
```

## Partitioning Strategies

### Even Distribution (Default)

Splits layers evenly across nodes:

```python
cluster = registry.create_cluster(
    name="my-cluster",
    node_urls=[...],
    model="llama2:70b",
    partitioning_strategy="even"
)

# 80 layers across 2 nodes:
# Node 1: 40 layers (0-39)
# Node 2: 40 layers (40-79)
```

### Memory-Aware Distribution

Allocates layers proportionally to available memory:

```python
cluster = registry.create_cluster(
    name="my-cluster",
    node_urls=[...],
    model="llama2:70b",
    partitioning_strategy="memory_aware"
)

# If Node 1 has 48GB and Node 2 has 24GB:
# Node 1: 53 layers (0-52)  # 66% of layers
# Node 2: 27 layers (53-79)  # 33% of layers
```

## Supported Models

### Large Models (Require Partitioning)

- **llama2:70b** - 80 layers, ~36GB memory
- **llama3:70b** - 80 layers, ~36GB memory
- **mixtral:8x7b** - 32 layers (MoE), ~26GB memory

### Small Models (Single Node)

- **llama3.2** - 32 layers, ~2GB memory
- **phi** - 32 layers, ~1.5GB memory
- **codellama:7b** - 32 layers, ~4GB memory

## Adding Custom Models

Edit `sollol/node_cluster.py` to add model specs:

```python
MODEL_SPECS = {
    "your-model:70b": ModelSpec(
        name="your-model:70b",
        total_layers=80,
        memory_per_layer_mb=450,
        min_memory_mb=4096
    ),
}
```

## Health Checking

Clusters require ALL nodes to be healthy:

```python
# Check cluster health
is_healthy = await cluster.health_check()

if not is_healthy:
    print(f"Cluster unhealthy - nodes down: {[n.url for n in cluster.nodes if not n.is_healthy]}")

# Check all clusters
cluster_health = await registry.health_check_clusters()
```

## Complete Example

```python
import asyncio
from sollol.registry import NodeRegistry

async def main():
    # Setup registry
    registry = NodeRegistry()

    # Discover nodes on network
    registry.discover_nodes(cidr="192.168.1.0/24")

    # Create cluster for large model
    if len(registry.get_healthy_nodes()) >= 2:
        cluster = registry.create_cluster(
            name="llama70b",
            node_urls=[
                registry.get_healthy_nodes()[0].url,
                registry.get_healthy_nodes()[1].url
            ],
            model="llama2:70b"
        )

        # Run inference
        result = await cluster.generate(
            prompt="Write a detailed explanation of quantum entanglement",
            options={"temperature": 0.7}
        )

        print(result['response'])
        print(f"\nCluster info: {result['_cluster']}")

    # Small models use individual nodes
    worker = registry.get_worker_for_model("llama3.2")
    print(f"Small model routed to: {worker.name}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Performance Characteristics

### Latency Trade-offs

- **Single Node**: Fastest (no inter-node communication)
- **Cluster (2 nodes)**: ~10-20% slower due to coordination overhead
- **Cluster (3+ nodes)**: Additional latency per node

### Throughput Benefits

- **Load Balancing**: Small models spread across available nodes
- **Large Model Access**: Run models impossible on single GPU
- **Mixed Workloads**: Clusters handle 70B while other nodes serve 7B/13B

### Optimal Configurations

**2-Node Cluster (Recommended for 70B models)**
```
GPU 1: 24GB - Layers 0-39 of Llama-70B
GPU 2: 24GB - Layers 40-79 of Llama-70B
```

**3-Node Cluster (For extremely large or multiple 70B models)**
```
GPU 1: 24GB - Layers 0-26
GPU 2: 24GB - Layers 27-53
GPU 3: 24GB - Layers 54-79
```

## Limitations

Current implementation:
- ✅ Layer partitioning logic and cluster management
- ✅ Health checking and failover
- ✅ Smart routing (large → cluster, small → single)
- ⚠️  Inter-node communication (basic implementation)
- ⚠️  Requires Ollama layer partitioning support (WIP upstream)

**Future enhancements:**
1. gRPC for faster inter-node communication
2. Session affinity for multi-turn conversations
3. Dynamic layer rebalancing based on load
4. Automatic cluster creation on demand

## Comparison: SOLLOL vs OLLOL

| Feature | SOLLOL | OLLOL (K2/olol) |
|---------|--------|-----------------|
| Load balancing | ✅ Advanced | ✅ Basic |
| Layer partitioning | ✅ New | ✅ Existing |
| Health scoring | ✅ Performance-based | ✅ Simple ping |
| Auto-discovery | ✅ CIDR scanning | ✅ Broadcast |
| Intelligent routing | ✅ Task-aware | ❌ |
| Priority queuing | ✅ | ❌ |
| Observability | ✅ Dashboard | ❌ |

SOLLOL now provides **both** capabilities from OLLOL:
- Load balancing across independent workers (existing)
- Layer partitioning for large models (new)

## See Also

- [Node Registry Documentation](./registry.md)
- [Intelligent Routing](./routing.md)
- [Network Discovery](./discovery.md)
