# SOLLOL - Super Ollama Load Balancer

[![Tests](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml/badge.svg)](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/tests.yml)
[![Lint](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/lint.yml/badge.svg)](https://github.com/BenevolentJoker-JohnL/SOLLOL/actions/workflows/lint.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Intelligent orchestration layer for distributed Ollama deployments with context-aware routing, resource-based scheduling, and adaptive learning.**

SOLLOL goes beyond simple load balancing to provide **intelligent request routing** based on task analysis, real-time performance metrics, and resource availability. Unlike round-robin balancers, SOLLOL understands what each request needs and routes it to the optimal node.

📊 **[Performance Benchmarks](BENCHMARKS.md)** | 📐 **[Architecture](ARCHITECTURE.md)** | 🤝 **[Contributing](CONTRIBUTING.md)**

---

## Why SOLLOL?

### Without SOLLOL (Basic Setup)
```python
# Direct Ollama - single node, no intelligence
response = requests.post("http://localhost:11434/api/chat", json=payload)
```
❌ Single point of failure
❌ No load balancing
❌ Random/round-robin routing
❌ No failover
❌ No performance optimization

### With SOLLOL (Intelligent Orchestration)
```python
# SOLLOL - distributed, intelligent, fault-tolerant
sollol = connect()
response = sollol.chat("Your prompt", priority=8)
```
✅ **38% faster** - Intelligent routing to optimal nodes
✅ **3.6pp higher success rate** - Automatic failover
✅ **78% GPU utilization** - Resource-aware scheduling
✅ **Transparent routing** - See where each request goes
✅ **Adaptive learning** - Improves over time

See [BENCHMARKS.md](BENCHMARKS.md) for detailed performance data.

---

## Features

### 🧠 Intelligent Routing Engine
- **Context-Aware Analysis**: Automatically detects task types (generation, embedding, classification, extraction, summarization, analysis)
- **Complexity Estimation**: Analyzes token count and conversation depth to predict resource needs
- **Multi-Factor Scoring**: Selects optimal nodes based on:
  - Availability & health status
  - Resource adequacy (GPU memory, CPU capacity)
  - Current performance (latency, success rate)
  - System load & utilization
  - Priority alignment & task specialization

### 🎯 Priority Queue System
- **Priority Levels**: 1-10 scale (10 = critical, 5 = normal, 1 = batch)
- **Age-Based Fairness**: Prevents starvation of low-priority tasks
- **Queue Metrics**: Real-time wait time tracking per priority level
- **Async-Friendly**: Non-blocking queue operations

### 🔄 Dynamic Failover & Recovery
- **Automatic Retry**: 3 attempts with exponential backoff
- **Host Exclusion**: Temporarily removes failing hosts from pool
- **Health Recovery**: Periodic re-checks of unavailable hosts
- **Graceful Degradation**: Continues operation with reduced capacity

### 📊 Advanced Observability
- **Real-Time Dashboard**: Live HTML dashboard showing routing decisions and performance
- **Routing Intelligence**: Transparent decision-making with reasoning logs
- **Performance Learning**: Records actual durations to improve future predictions
- **Alert System**: Automatic detection of degraded hosts and performance issues

### ⚡ High Performance
- **Ray Integration**: Fast, concurrent request handling with Ray actors
- **Dask Batch Processing**: Distributed batch embeddings for large document collections
- **Autonomous Autobatch**: Continuously processes queued documents without manual intervention
- **Adaptive Metrics Loop**: Dynamically updates host performance data in real-time
- **Routing Overhead**: < 10ms per request
- **Latency Reduction**: 20-40% improvement vs random routing

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

```
Client Request
      │
      ▼
┌─────────────────────────────────────────────────┐
│     SOLLOL FastAPI Gateway (Port 8000)          │
│  ┌───────────────────────────────────────────┐  │
│  │   INTELLIGENT ROUTING ENGINE              │  │
│  │  1. Request Analysis                      │  │
│  │     - Task type detection                 │  │
│  │     - Complexity estimation               │  │
│  │     - Resource prediction                 │  │
│  │  2. Context Scoring                       │  │
│  │     - Multi-factor node evaluation        │  │
│  │     - Performance + Resource weighting    │  │
│  │  3. Optimal Selection                     │  │
│  │     - Best node with decision reasoning   │  │
│  └───────────────────────────────────────────┘  │
└──────┬──────────────────────────────────────────┘
       │
       ▼
   Ray/Dask Workers → OLLOL Nodes (GPU/CPU)
       │
       └─→ Adaptive Metrics Feedback Loop
```

## Installation

```bash
pip install sollol
```

Or from source:
```bash
git clone https://github.com/BenevolentJoker-JohnL/SOLLOL.git
cd SOLLOL
pip install -e .
```

## Quick Start

### Option 1: Plug-and-Play Client (Simplest)

```python
from sollol import connect

# One-line connection - that's it!
sollol = connect()

# Immediately use intelligent routing
response = sollol.chat("Explain quantum computing")
print(response['message']['content'])

# See where it was routed
routing = response['_sollol_routing']
print(f"✓ Routed to: {routing['host']}")
print(f"✓ Task type: {routing['task_type']}")
print(f"✓ Duration: {routing['actual_duration_ms']:.0f}ms")
```

**That's it!** SOLLOL handles:
- ✅ Intelligent routing based on request complexity
- ✅ Automatic failover and retry
- ✅ Performance tracking and learning
- ✅ Priority-based scheduling

### Option 2: Full Server Deployment

```python
from sollol import SOLLOL, SOLLOLConfig

# Configure SOLLOL server
config = SOLLOLConfig(
    ray_workers=4,
    dask_workers=4,
    hosts=["127.0.0.1:11434", "10.0.0.2:11434"],
    autobatch_interval=30,
    routing_strategy="performance"
)

# Start SOLLOL server (non-blocking)
sollol = SOLLOL(config)
sollol.start(blocking=False)

# Your application continues...
# SOLLOL gateway now running at http://localhost:8000
```

### Option 2: CLI (For Standalone Deployment)

```bash
# Start with default settings (2 Ray workers, 2 Dask workers)
python -m sollol.cli up

# Or customize:
python -m sollol.cli up --workers 4 --dask-workers 4 --port 8000
```

**Note:** The CLI uses `config/hosts.txt` to load OLLOL hosts:

```
# config/hosts.txt
127.0.0.1:11434
10.0.0.2:11434
10.0.0.3:11434
```

### 3. Send Requests

```bash
# Chat completion with priority
curl -X POST "http://localhost:8000/api/chat?priority=8" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Analyze this data and extract key insights..."}]
  }'

# Response includes routing metadata:
{
  "message": {...},
  "_sollol_routing": {
    "host": "10.0.0.2:11434",
    "task_type": "analysis",
    "complexity": "medium",
    "decision_score": 185.3,
    "actual_duration_ms": 2341.2
  }
}

# Embedding (single)
curl -X POST http://localhost:8000/api/embed \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a test document",
    "model": "nomic-embed-text"
  }'

# Batch embedding (queued for autobatch)
curl -X POST http://localhost:8000/api/embed/batch \
  -H "Content-Type: application/json" \
  -d '{
    "docs": ["Document 1", "Document 2", "Document 3"]
  }'
```

### 4. Monitor Performance

```bash
# Real-time dashboard (open in browser)
open dashboard.html
# Or navigate to: file:///path/to/sollol/dashboard.html
# Dashboard auto-refreshes every 3 seconds showing:
#   - System status and alerts
#   - Host performance metrics
#   - Routing intelligence patterns
#   - Resource utilization

# Check health
curl http://localhost:8000/api/health

# View statistics
curl http://localhost:8000/api/stats

# Dashboard API (powers the HTML dashboard)
curl http://localhost:8000/api/dashboard

# Prometheus metrics
curl http://localhost:9090/metrics
```

## Configuration

### Programmatic Configuration

The `SOLLOLConfig` class provides full control over SOLLOL behavior:

```python
from sollol import SOLLOLConfig

config = SOLLOLConfig(
    # Ray configuration
    ray_workers=4,                    # Number of Ray actor workers

    # Dask configuration
    dask_workers=4,                   # Number of Dask workers
    dask_scheduler=None,              # External scheduler (optional)

    # OLLOL hosts
    hosts=["127.0.0.1:11434"],        # List of Ollama instances

    # Gateway configuration
    gateway_port=8000,                # FastAPI port
    gateway_host="0.0.0.0",           # FastAPI host

    # Routing strategy
    routing_strategy="performance",   # "performance", "round_robin", or "priority"

    # Autobatch configuration
    autobatch_enabled=True,           # Enable batch processing
    autobatch_interval=60,            # Seconds between batches
    autobatch_min_batch_size=1,       # Min docs to trigger batch
    autobatch_max_batch_size=100,     # Max docs per batch

    # Metrics configuration
    metrics_enabled=True,             # Enable Prometheus metrics
    metrics_port=9090,                # Metrics server port

    # Adaptive metrics
    adaptive_metrics_enabled=True,    # Enable dynamic routing
    adaptive_metrics_interval=30,     # Metric update interval (seconds)

    # Health checks
    health_check_enabled=True,        # Enable health monitoring
    health_check_interval=120,        # Health check interval (seconds)

    # Retry configuration
    max_retries=3,                    # Max retry attempts
    retry_backoff_multiplier=0.5,     # Backoff multiplier

    # Timeouts
    chat_timeout=300.0,               # Chat timeout (seconds)
    embedding_timeout=60.0,           # Embedding timeout (seconds)
)
```

**Dynamic Updates:**

```python
# Update configuration at runtime
sollol.update_config(
    ray_workers=6,
    autobatch_interval=45
)

# Some changes require restart
sollol.stop()
sollol.start()
```

**Status Monitoring:**

```python
# Get current status
status = sollol.get_status()
print(status)

# Get health information
health = sollol.get_health()

# Get performance statistics
stats = sollol.get_stats()
```

### CLI Options

```bash
python -m sollol.cli up --help

Options:
  --workers INTEGER              Number of Ray worker actors [default: 2]
  --dask-workers INTEGER         Number of Dask workers [default: 2]
  --hosts TEXT                   Path to OLLOL hosts file [default: config/hosts.txt]
  --port INTEGER                 FastAPI gateway port [default: 8000]
  --dask-scheduler TEXT          External Dask scheduler (e.g., tcp://10.0.0.1:8786)
  --autobatch / --no-autobatch   Enable autonomous batch processing [default: True]
  --autobatch-interval INTEGER   Seconds between autobatch cycles [default: 60]
  --adaptive-metrics / --no-adaptive-metrics
                                 Enable adaptive metrics feedback loop [default: True]
  --adaptive-metrics-interval INTEGER
                                 Seconds between metrics updates [default: 30]
```

### Multi-Machine Setup

**On Machine 1 (Dask Scheduler)**:
```bash
dask scheduler
# Note the scheduler address (e.g., tcp://10.0.0.1:8786)
```

**On Machine 2+ (SOLLOL Gateways)**:
```bash
python -m sollol.cli up --dask-scheduler tcp://10.0.0.1:8786
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat completion with **intelligent routing** (supports `?priority=1-10`) |
| `/api/embed` | POST | Single document embedding (synchronous) |
| `/api/embed/batch` | POST | Queue documents for batch embedding |
| `/api/health` | GET | Health check for gateway and hosts |
| `/api/stats` | GET | Performance statistics + **routing intelligence data** |
| `/api/dashboard` | GET | **Real-time dashboard data** (system status, alerts, routing patterns) |
| `/api/batch-status` | GET | Dask batch processing status |
| `/docs` | GET | Interactive API documentation |

## Intelligent Routing

### How It Works

**Step 1: Request Analysis**
```python
context = router.analyze_request(payload, priority=8)
# Detects: task_type='generation', complexity='medium', requires_gpu=True
```

**Step 2: Multi-Factor Scoring**

SOLLOL scores each available host using 7 factors:

```python
score = baseline (100.0)
score *= success_rate                    # Factor 1: Performance history
score /= (1 + latency_penalty)          # Factor 2: Current latency
score *= gpu_bonus (if required)        # Factor 3: GPU availability
score /= (1 + load_penalty)             # Factor 4: CPU load
score *= priority_bonus                 # Factor 5: Priority alignment
score *= task_specialization_bonus     # Factor 6: Task-type match
score /= (1 + duration_penalty)        # Factor 7: Resource headroom
```

**Step 3: Optimal Selection**

The highest-scoring host is selected with full decision transparency:

```json
{
  "selected_host": "10.0.0.2:11434",
  "score": 185.3,
  "reasoning": "Task: generation (medium); Host 10.0.0.2:11434: latency=120.1ms, success=98.2%; GPU preferred: 16384MB available",
  "alternatives": [...]
}
```

**Step 4: Performance Learning**

After execution, SOLLOL records actual duration to improve future predictions:
- Builds performance history per task-type + model
- Adapts routing decisions based on real-world results
- Continuously optimizes for your specific workload

## Monitoring

### Real-Time Dashboard

Open `dashboard.html` in your browser for live monitoring:

- **System Status**: Health, active hosts, workers, GPU memory
- **Host Performance**: Per-host latency, success rate, load, GPU availability
- **Active Alerts**: Automatic detection of degraded/offline hosts
- **Routing Intelligence**: Learned task patterns and performance history
- **Auto-Refresh**: Updates every 3 seconds

### Dashboard API

```bash
curl http://localhost:8000/api/dashboard | jq
```

```json
{
  "status": {
    "healthy": true,
    "total_hosts": 3,
    "available_hosts": 3,
    "ray_workers": 4,
    "dask_available": true
  },
  "performance": {
    "avg_latency_ms": 156.3,
    "avg_success_rate": 0.982,
    "total_gpu_memory_mb": 24576
  },
  "routing": {
    "intelligent_routing_enabled": true,
    "task_types_learned": 5,
    "patterns_available": ["generation", "embedding", "classification"]
  },
  "alerts": [
    {
      "severity": "warning",
      "message": "Host 10.0.0.3:11434 has high latency: 823ms",
      "timestamp": "2025-10-02T18:30:15.123456"
    }
  ],
  "hosts": [...]
}
```

### Statistics API

```bash
curl http://localhost:8000/api/stats | jq
```

Provides comprehensive routing intelligence:
- Per-host performance metrics
- Learned performance patterns by task type + model
- Performance history statistics (avg, min, max durations)
- Routing decision patterns

### Prometheus Metrics

SOLLOL exposes Prometheus metrics on port 9090:

```
# Request metrics
sollol_requests_total{endpoint="chat",status="success"} 1523
sollol_request_latency_seconds{endpoint="chat"} 0.234

# Host metrics
sollol_host_latency_ms{host="10.0.0.2:11434"} 156.3
sollol_host_success_rate{host="10.0.0.2:11434"} 0.982

# Worker metrics
sollol_worker_failures_total{host="10.0.0.3:11434"} 12
sollol_active_requests 3
```

## Examples

See the `examples/` directory for complete usage examples:

- **`basic_usage.py`**: Simple usage with default and custom configurations
- **`application_integration.py`**: Embedding SOLLOL in a Python application (like SynapticLlamas)
- **`multi_machine_setup.py`**: Distributed deployment across multiple machines with various optimization strategies

Run examples:

```bash
# Basic usage
python examples/basic_usage.py

# Application integration
python examples/application_integration.py

# Multi-machine setups
python examples/multi_machine_setup.py machine1
python examples/multi_machine_setup.py gpu-heavy
python examples/multi_machine_setup.py low-latency
```

## Development

### Project Structure

```
sollol/
├── src/sollol/
│   ├── __init__.py           # Public API exports (SOLLOL, SOLLOLConfig)
│   ├── sollol.py             # Main orchestration class
│   ├── config.py             # Configuration dataclass
│   ├── cli.py                # CLI entry point
│   ├── gateway.py            # FastAPI server with intelligent routing
│   ├── intelligence.py       # 🧠 Context-aware routing engine
│   ├── prioritization.py     # 🎯 Priority queue system
│   ├── workers.py            # Ray actors for OLLOL requests
│   ├── cluster.py            # Ray + Dask initialization
│   ├── batch.py              # Dask batch processing
│   ├── autobatch.py          # Autonomous batch pipeline
│   ├── memory.py             # Host management + routing
│   ├── metrics.py            # Prometheus metrics
│   └── adaptive_metrics.py   # Dynamic metrics feedback loop
├── examples/
│   ├── basic_usage.py        # Simple usage examples
│   ├── application_integration.py  # App embedding example
│   └── multi_machine_setup.py     # Distributed setups
├── config/
│   └── hosts.txt             # OLLOL host configuration (CLI only)
├── dashboard.html            # 📊 Real-time monitoring dashboard
├── ARCHITECTURE.md           # 📐 Detailed system design
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Troubleshooting

### No hosts available

**Problem**: `{"error": "No available OLLOL hosts"}`

**Solution**:
1. Check `config/hosts.txt` has valid hosts
2. Verify Ollama is running: `curl http://127.0.0.1:11434/api/tags`
3. Check health: `curl http://localhost:8000/api/health`

### Ray workers not starting

**Problem**: Ray initialization fails

**Solution**:
```bash
# Kill existing Ray processes
pkill -f "ray::"

# Restart SOLLOL
python -m sollol.cli up
```

### Dask connection issues

**Problem**: Cannot connect to Dask scheduler

**Solution**:
```bash
# Check scheduler is running
dask scheduler

# Verify connection
python -c "from dask.distributed import Client; c = Client('tcp://10.0.0.1:8786'); print(c)"
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

- Built with [Ray](https://github.com/ray-project/ray), [Dask](https://github.com/dask/dask), and [FastAPI](https://github.com/tiangolo/fastapi)
- Designed for [Ollama](https://github.com/ollama/ollama)
- Inspired by modern load balancing patterns and distributed computing research

---

## Real-World Integration Examples

### Integrate with Your AI Application (3 lines of code!)

```python
from sollol import connect

# Replace your direct Ollama calls with SOLLOL
sollol = connect()  # One line!

# All your AI requests now use intelligent routing
response = sollol.chat("Your prompt", priority=8)
```

### Example: RAG Application

```python
from sollol import connect

sollol = connect()

# Document processing with intelligent routing
class RAGPipeline:
    def process_documents(self, docs):
        # Batch embed documents (routed to optimal CPU nodes)
        sollol.batch_embed(docs)

    def query(self, question):
        # High-priority user query (routed to best GPU node)
        return sollol.chat(
            message=question,
            priority=8,  # High priority
            system_prompt="You are a helpful RAG assistant"
        )
```

### Example: Multi-Agent System

```python
from sollol import connect

sollol = connect()

class AgentSystem:
    def coordinator_agent(self, task):
        # Critical coordination task
        return sollol.chat(task, priority=10)

    def worker_agent(self, subtask):
        # Normal priority worker
        return sollol.chat(subtask, priority=5)

    def analyst_agent(self, data):
        # Background analysis
        return sollol.chat(data, priority=3)
```

---

## What Makes SOLLOL "Portfolio-Shiny"?

Unlike simple load balancers that use round-robin or random selection, SOLLOL is an **intelligent orchestration platform** that showcases advanced distributed systems skills:

1. **Context-Aware Intelligence**: Analyzes request content to understand task requirements before routing
2. **Multi-Factor Optimization**: 7-factor scoring algorithm balancing performance, resources, and priorities
3. **Adaptive Learning**: Records actual performance to improve future routing decisions
4. **Production-Grade Observability**: Real-time dashboards, routing transparency, and comprehensive metrics
5. **Enterprise Features**: Priority queues, dynamic failover, resource-aware scheduling, graceful degradation
6. **Plug-and-Play Integration**: One-line connection for any AI application

**Technical highlights for portfolio reviewers:**
- Custom request classification engine with regex-based task detection
- Resource-aware scheduling with GPU memory and CPU load weighting
- Priority queue implementation with age-based fairness
- Automatic retry with exponential backoff and host exclusion
- Real-time metrics aggregation and performance tracking
- RESTful API design with full OpenAPI documentation
- Production-ready error handling and health monitoring
- Zero-config client SDK with async support

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

---

**SOLLOL** - Because intelligent routing is the difference between a load balancer and an orchestration platform. 🚀
