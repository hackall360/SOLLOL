# SOLLOL - Super Ollama Load Balancer

**Performance-aware load balancing for Ollama with Ray, Dask, and adaptive routing.**

SOLLOL automatically distributes Ollama requests across multiple nodes with intelligent routing based on real-time performance metrics. It supports both live queries via Ray and batch processing via Dask, with autonomous embedding pipelines and comprehensive monitoring.

## Features

- ✨ **Performance-Aware Routing**: Automatically routes requests to the optimal OLLOL node based on latency, success rate, and system load
- 🚀 **Ray Integration**: Fast, concurrent request handling with Ray actors
- 📦 **Dask Batch Processing**: Distributed batch embeddings for large document collections
- 🔄 **Autonomous Autobatch**: Continuously processes queued documents without manual intervention
- 📊 **Prometheus Metrics**: Built-in metrics server for monitoring and observability
- 🔧 **Adaptive Metrics Loop**: Dynamically updates host performance data in real-time
- ❤️ **Health Checks**: Periodic health monitoring with automatic failover
- 🎯 **Zero Configuration**: Works out-of-the-box with localhost, scales to multi-node clusters

## Architecture

```
┌──────────────┐
│   Client     │
└──────┬───────┘
       │
       v
┌──────────────────────────────────────────────┐
│         FastAPI Gateway (port 8000)          │
│  ┌────────────────────────────────────────┐  │
│  │  Performance-Aware Routing Engine      │  │
│  │  - Latency tracking                    │  │
│  │  - Success rate monitoring             │  │
│  │  - Adaptive metrics feedback           │  │
│  └────────────────────────────────────────┘  │
└──────┬────────────────────────────┬──────────┘
       │                            │
       v                            v
┌──────────────┐            ┌──────────────┐
│  Ray Actors  │            │ Dask Workers │
│  (Live Reqs) │            │ (Batch Jobs) │
└──────┬───────┘            └──────┬───────┘
       │                            │
       └────────────┬───────────────┘
                    │
       ┌────────────┴───────────────┐
       │                            │
       v                            v
┌──────────────┐            ┌──────────────┐
│ OLLOL Node 1 │            │ OLLOL Node 2 │
│ (10.0.0.2)   │            │ (10.0.0.3)   │
└──────────────┘            └──────────────┘
```

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/sollol.git
cd sollol

# Install dependencies
pip install -e .

# Or install from PyPI (when published)
pip install sollol
```

## Quick Start

### Option 1: Programmatic API (Recommended for Applications)

```python
from sollol import SOLLOL, SOLLOLConfig

# Configure SOLLOL
config = SOLLOLConfig(
    ray_workers=4,
    dask_workers=4,
    hosts=["127.0.0.1:11434", "10.0.0.2:11434"],
    autobatch_interval=30,
    routing_strategy="performance"
)

# Initialize and start (non-blocking)
sollol = SOLLOL(config)
sollol.start(blocking=False)

# Your application continues here...
# SOLLOL is now running at http://localhost:8000

# Check status
status = sollol.get_status()
print(f"Running: {status['running']}")

# Stop when done
sollol.stop()
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
# Chat completion
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

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
# Check health
curl http://localhost:8000/api/health

# View statistics
curl http://localhost:8000/api/stats

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
| `/api/chat` | POST | Chat completion with performance routing |
| `/api/embed` | POST | Single document embedding (synchronous) |
| `/api/embed/batch` | POST | Queue documents for batch embedding |
| `/api/health` | GET | Health check for gateway and hosts |
| `/api/stats` | GET | Performance statistics for all hosts |
| `/api/batch-status` | GET | Dask batch processing status |
| `/docs` | GET | Interactive API documentation |

## Performance Routing

SOLLOL uses a weighted scoring system to select the optimal host for each request:

```python
score = (cpu_load × 0.3) +
        (1 / gpu_free_mem × 0.2) +
        (priority × 0.1) +
        (latency_ms / 1000 × 0.2) +
        ((1 - success_rate) × 0.2)
```

Lower scores are better. The system:
- Tracks latency and success rate for every request
- Updates metrics every 30 seconds (configurable)
- Automatically fails over to healthy nodes
- Re-checks unhealthy nodes periodically

## Monitoring

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

### Statistics API

```bash
curl http://localhost:8000/api/stats | jq
```

```json
{
  "hosts": [
    {
      "host": "10.0.0.2:11434",
      "available": true,
      "latency_ms": 156.3,
      "success_rate": 0.982,
      "cpu_load": 0.45,
      "gpu_free_mem": 8192,
      "priority": 0,
      "last_updated": "2025-10-02T18:30:15.123456"
    }
  ],
  "timestamp": "2025-10-02T18:30:20.000000"
}
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
│   ├── __init__.py         # Public API exports (SOLLOL, SOLLOLConfig)
│   ├── sollol.py           # Main orchestration class
│   ├── config.py           # Configuration dataclass
│   ├── cli.py              # CLI entry point
│   ├── gateway.py          # FastAPI server with routing
│   ├── workers.py          # Ray actors for OLLOL requests
│   ├── cluster.py          # Ray + Dask initialization
│   ├── batch.py            # Dask batch processing
│   ├── autobatch.py        # Autonomous batch pipeline
│   ├── memory.py           # Host management + routing
│   ├── metrics.py          # Prometheus metrics
│   └── adaptive_metrics.py # Dynamic metrics feedback loop
├── examples/
│   ├── basic_usage.py      # Simple usage examples
│   ├── application_integration.py  # App embedding example
│   └── multi_machine_setup.py     # Distributed setups
├── config/
│   └── hosts.txt           # OLLOL host configuration (CLI only)
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

**SOLLOL** - Because your Ollama deserves intelligent routing. 🚀
