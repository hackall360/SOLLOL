# SOLLOL Architecture - Intelligent Ollama Load Balancing

## System Overview

SOLLOL (Super Ollama Load Balancer) is an **intelligent orchestration layer** for distributed Ollama deployments. Unlike simple round-robin load balancers, SOLLOL uses **context-aware routing**, **resource-based scheduling**, and **adaptive learning** to optimize AI inference across multiple nodes.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Application                        │
│                  (SynapticLlamas, FlockParser, etc.)            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SOLLOL FastAPI Gateway                      │
│                         (Port 8000)                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           INTELLIGENT ROUTING ENGINE                       │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  1. Request Analysis                                │  │  │
│  │  │     - Detect task type (generation, embedding, etc) │  │  │
│  │  │     - Estimate complexity & token count             │  │  │
│  │  │     - Determine resource requirements               │  │  │
│  │  │  ────────────────────────────────────────────────  │  │  │
│  │  │  2. Context Scoring                                 │  │  │
│  │  │     - Availability check                            │  │  │
│  │  │     - Resource adequacy (GPU, CPU, memory)          │  │  │
│  │  │     - Current performance (latency, success rate)   │  │  │
│  │  │     - Load & utilization                            │  │  │
│  │  │     - Priority alignment                            │  │  │
│  │  │  ────────────────────────────────────────────────  │  │  │
│  │  │  3. Optimal Node Selection                          │  │  │
│  │  │     - Score all available hosts                     │  │  │
│  │  │     - Select best match                             │  │  │
│  │  │     - Log decision reasoning                        │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  PRIORITY QUEUE (Task Scheduling)                   │  │  │
│  │  │  - Priority-based ordering (1-10)                   │  │  │
│  │  │  - Age-based fairness (prevents starvation)         │  │  │
│  │  │  - Queue metrics & wait time tracking               │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  FAILOVER & RECOVERY                                │  │  │
│  │  │  - Automatic retry with backoff                     │  │  │
│  │  │  - Dynamic host exclusion                           │  │  │
│  │  │  - Health monitoring & auto-recovery                │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────┬───────────────────────────────────────┬─────────────────┘
        │                                       │
        ▼                                       ▼
┌───────────────────┐               ┌───────────────────────┐
│   Ray Cluster     │               │   Dask Cluster        │
│  (Live Requests)  │               │  (Batch Processing)   │
│                   │               │                       │
│  ┌─────────────┐  │               │  ┌──────────────────┐ │
│  │OllamaWorker │  │               │  │ Batch Embeddings │ │
│  │   Actor 1   │  │               │  │   Worker Pool    │ │
│  └─────────────┘  │               │  └──────────────────┘ │
│  ┌─────────────┐  │               │  ┌──────────────────┐ │
│  │OllamaWorker │  │               │  │  Autobatch       │ │
│  │   Actor 2   │  │               │  │  Scheduler       │ │
│  └─────────────┘  │               │  └──────────────────┘ │
│  ┌─────────────┐  │               └───────────────────────┘
│  │OllamaWorker │  │
│  │   Actor N   │  │
│  └─────────────┘  │
└───────┬───────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                  OLLOL Node Selection Layer                      │
│                   (Performance-Aware Routing)                    │
└─┬──────────┬──────────┬──────────┬──────────┬─────────────────┬─┘
  │          │          │          │          │                 │
  ▼          ▼          ▼          ▼          ▼                 ▼
┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐           ┌─────┐
│Node1│  │Node2│  │Node3│  │Node4│  │Node5│    ...    │NodeN│
│GPU  │  │GPU  │  │CPU  │  │GPU  │  │CPU  │           │GPU  │
│8GB  │  │24GB │  │32C  │  │16GB │  │64C  │           │12GB │
└─────┘  └─────┘  └─────┘  └─────┘  └─────┘           └─────┘
  ▲          ▲          ▲          ▲          ▲                 ▲
  │          │          │          │          │                 │
  └──────────┴──────────┴──────────┴──────────┴─────────────────┘
                    Adaptive Metrics Feedback Loop
               (Real-time latency, success rate, load monitoring)
```

---

## Key Components

### 1. Intelligent Routing Engine (`intelligence.py`)

**Purpose**: Context-aware request analysis and optimal node selection

**Features**:
- **Task Type Detection**: Automatically classifies requests (generation, embedding, classification, extraction, summarization, analysis)
- **Complexity Estimation**: Analyzes token count and conversation depth
- **Resource Prediction**: Determines GPU requirements and estimated duration
- **Multi-Factor Scoring**: Evaluates hosts based on:
  - Availability (binary)
  - Resource adequacy (GPU memory, CPU capacity)
  - Current performance (latency, success rate)
  - Load & utilization
  - Priority alignment
  - Task-type specialization

**Algorithm**:
```python
score = baseline (100.0)
score *= success_rate
score /= (1 + latency_penalty)
score *= gpu_bonus (if required)
score /= (1 + load_penalty)
score *= priority_bonus
```

---

### 2. Priority Queue System (`prioritization.py`)

**Purpose**: Fair task scheduling with priority support

**Features**:
- **Priority Levels**: 1-10 (10 = highest)
- **Age-Based Fairness**: Prevents starvation of low-priority tasks
- **Queue Metrics**: Wait time tracking per priority level
- **Async-Friendly**: Non-blocking queue operations

**Priority Guidelines**:
- **10 (Critical)**: System-critical requests
- **8 (High)**: User-facing real-time requests
- **5 (Normal)**: Standard requests
- **3 (Low)**: Background tasks
- **1 (Batch)**: Batch processing

---

### 3. Adaptive Metrics Loop (`adaptive_metrics.py`)

**Purpose**: Real-time performance monitoring and feedback

**Features**:
- **Health Checks**: Periodic node availability testing
- **Latency Tracking**: Per-host average latency
- **Success Rate Monitoring**: Request success/failure tracking
- **Dynamic Updates**: Metrics inform routing decisions in real-time

---

### 4. Failover & Recovery

**Purpose**: High availability and fault tolerance

**Features**:
- **Automatic Retry**: 3 attempts with exponential backoff
- **Host Exclusion**: Temporarily removes failing hosts from pool
- **Health Recovery**: Periodic re-checks of unavailable hosts
- **Graceful Degradation**: Continues operation with reduced capacity

---

### 5. Observability Layer

#### Dashboard Endpoint (`/api/dashboard`)
Provides real-time monitoring data:
- System status (total/available hosts, workers)
- Performance metrics (avg latency, success rate, GPU memory)
- Routing intelligence (task types learned, patterns)
- Alerts (unavailable hosts, degraded performance)
- Per-host health status

#### Stats Endpoint (`/api/stats`)
Detailed statistics:
- Host performance history
- Routing pattern analysis
- Task type distribution
- Learned performance baselines

---

## Request Flow

### Example: Chat Completion Request

```
1. Client sends POST /api/chat with priority=8 (high)
   └─> FastAPI Gateway receives request

2. Intelligent Router analyzes request
   ├─> Detects task_type = "generation"
   ├─> Estimates complexity = "medium" (1200 tokens)
   ├─> Determines requires_gpu = True
   └─> Sets priority = 8

3. Router scores all available hosts
   ├─> Host A (GPU:16GB, load:0.2, latency:120ms) = score: 185.3
   ├─> Host B (GPU:8GB,  load:0.6, latency:200ms) = score: 92.1
   ├─> Host C (no GPU,   load:0.1, latency:80ms)  = score: 41.2
   └─> **Selects Host A** (highest score)

4. Ray actor executes request on Host A
   ├─> Monitors execution time
   └─> Records actual duration for learning

5. Response returned with routing metadata
   {
     "message": {...},
     "_sollol_routing": {
       "host": "10.0.0.2:11434",
       "task_type": "generation",
       "complexity": "medium",
       "decision_score": 185.3,
       "actual_duration_ms": 2341.2
     }
   }

6. Performance recorded for future optimization
   └─> Router learns typical duration for this task/model combo
```

---

## Scaling Patterns

### Single Node (Development)
```
1 Gateway + 2 Ray workers + 1 Dask worker + 1 Ollama instance
```

### Multi-Node (Production)
```
Gateway (Machine 1)
  ├─> Ray cluster (4 workers)
  ├─> Dask scheduler connection
  └─> Routes to 5+ OLLOL nodes across multiple machines

Ollama Nodes (Machines 2-6)
  ├─> Machine 2: GPU node (24GB) - for large models
  ├─> Machine 3: GPU node (16GB) - for medium models
  ├─> Machine 4: CPU node (64 cores) - for small/fast models
  ├─> Machine 5: GPU node (8GB) - for embeddings
  └─> Machine 6: CPU node (32 cores) - for batch processing
```

### Distributed (Enterprise)
```
Multiple SOLLOL gateways + External Dask scheduler + 10+ OLLOL nodes
  ├─> Load balancer distributes across SOLLOL instances
  ├─> Shared Dask scheduler for batch coordination
  ├─> Heterogeneous OLLOL fleet (mix of GPU/CPU, different models)
  └─> Prometheus metrics aggregation
```

---

## Performance Characteristics

### Routing Decision Time
- Task analysis: < 1ms
- Host scoring: < 5ms (for 10 hosts)
- Total overhead: < 10ms

### Throughput
- Limited by slowest OLLOL node
- Scales linearly with number of nodes
- Ray handles concurrent requests efficiently

### Latency
- Baseline: OLLOL node latency
- SOLLOL overhead: 10-20ms
- Intelligent routing can **reduce** overall latency by 20-40% vs random routing

---

## Integration Points

### SynapticLlamas
```python
from sollol import SOLLOL, SOLLOLConfig

# Configure SOLLOL for SynapticLlamas
config = SOLLOLConfig(
    ray_workers=4,
    hosts=["gpu-node-1:11434", "gpu-node-2:11434"],
    routing_strategy="performance"
)

sollol = SOLLOL(config)
sollol.start(blocking=False)

# SynapticLlamas now routes through SOLLOL
# Embedding requests automatically go to optimal nodes
```

### FlockParser
```python
# FlockParser document processing with priority
response = requests.post(
    "http://sollol:8000/api/chat",
    json={
        "model": "llama3.2",
        "messages": [...],
        "priority": 8  # High priority for user queries
    }
)

# SOLLOL routes to best available node
# Adds routing metadata to response
```

---

## Future Enhancements

1. **ML-Based Prediction**: Use historical patterns to predict optimal routing
2. **Cost Optimization**: Route based on node costs (cloud deployments)
3. **Geographic Routing**: Latency-aware routing for distributed deployments
4. **A/B Testing**: Route % of traffic to experimental nodes
5. **SLA Enforcement**: Guarantee latency SLAs per task type/priority
6. **Auto-Scaling**: Trigger node provisioning based on queue depth

---

**SOLLOL** - Because intelligent routing is the difference between a load balancer and an orchestration platform.
