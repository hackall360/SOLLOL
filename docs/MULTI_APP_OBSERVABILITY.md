# Multi-App Observability with SOLLOL

## Overview

SOLLOL v0.9.16+ supports **multi-app observability**, allowing multiple applications on the same machine to share a single unified dashboard instance. This provides centralized monitoring for all SOLLOL-powered applications without port conflicts or resource duplication.

## How It Works

### Automatic Fallback Mechanism

When a SOLLOL application attempts to start the Unified Dashboard:

1. **Port Check**: The dashboard checks if port 8080 (default) is already in use
2. **Fallback Detection**: If occupied, assumes another SOLLOL dashboard is running
3. **Graceful Fallback**: Logs connection info and continues without error
4. **Shared Observability**: Both applications use the same dashboard for monitoring

### Key Features

- ✅ **Zero Configuration**: Automatic detection and fallback
- ✅ **No Port Conflicts**: Multiple apps coexist peacefully
- ✅ **Centralized Monitoring**: Single dashboard for all applications
- ✅ **Graceful Degradation**: Apps continue running if dashboard unavailable

## Usage

### Basic Example

```python
from sollol import OllamaPool, UnifiedDashboard, RayHybridRouter

# Create application infrastructure
pool = OllamaPool(nodes=[{"host": "localhost", "port": 11434}])
router = RayHybridRouter(ollama_pool=pool, enable_distributed=True)

# Create dashboard with fallback enabled (default)
dashboard = UnifiedDashboard(router=router, dashboard_port=8080)

# Start dashboard - automatically falls back if port occupied
dashboard.run(allow_fallback=True)  # allow_fallback=True is default
```

### Expected Behavior

**First Application** (starts dashboard):
```
2025-10-07 09:00:00,000 - INFO - 🚀 Starting Unified Dashboard on http://0.0.0.0:8080
2025-10-07 09:00:00,100 - INFO - ✅ Using Waitress production server
```

**Second Application** (detects existing dashboard):
```
2025-10-07 09:01:00,000 - INFO - 📊 Dashboard already running on port 8080
2025-10-07 09:01:00,001 - INFO -    Connecting to existing dashboard at http://localhost:8080
2025-10-07 09:01:00,002 - INFO - ✅ Application will use shared dashboard for observability
```

## Configuration Options

### Dashboard Initialization

```python
dashboard = UnifiedDashboard(
    router=router,
    dashboard_port=8080,        # Dashboard port (default: 8080)
    ray_dashboard_port=8265,    # Ray dashboard port (default: 8265)
    dask_dashboard_port=8787,   # Dask dashboard port (default: 8787)
)
```

### Run Method

```python
dashboard.run(
    host="0.0.0.0",            # Bind address (default: 0.0.0.0)
    debug=False,               # Debug mode (default: False)
    allow_fallback=True        # Enable fallback detection (default: True)
)
```

### Disable Fallback (Force Start)

If you want to force the dashboard to start and fail if the port is occupied:

```python
dashboard.run(allow_fallback=False)
```

This will raise an `OSError` if the port is already in use.

## Architecture

### Dashboard Components

The Unified Dashboard provides monitoring for:

1. **Network Nodes**: Ollama pool nodes with health status
2. **RPC Backends**: llama.cpp RPC servers for model sharding
3. **Applications**: Registered applications using SOLLOL
4. **Request Metrics**: Real-time request/response stats
5. **Ray Dashboard**: Distributed task monitoring (port 8265)
6. **Dask Dashboard**: Batch processing monitoring (dynamic port)

### Multi-App Workflow

```
┌─────────────────┐         ┌─────────────────┐
│  Application 1  │         │  Application 2  │
│  (SynapticLlamas│         │  (CustomApp)    │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ 1. Start dashboard        │ 2. Detect existing
         │    on port 8080           │    dashboard on 8080
         │                           │
         ├───────────────┬───────────┤
         ▼               ▼           ▼
    ┌────────────────────────────────────┐
    │   Unified Dashboard (Port 8080)    │
    │                                    │
    │  • Network Nodes                   │
    │  • RPC Backends                    │
    │  • Applications: 2 registered      │
    │  • Request Metrics                 │
    │  • Ray Dashboard → :8265           │
    │  • Dask Dashboard → :auto          │
    └────────────────────────────────────┘
```

## Real-World Example

### SynapticLlamas Integration

```python
# In SynapticLlamas main.py
from sollol import UnifiedDashboard, RayHybridRouter
from sollol.dashboard_client import DashboardClient

# Create distributed router
router = RayHybridRouter(
    ollama_pool=ollama_pool,
    rpc_backends=rpc_backends,
    enable_distributed=True
)

# Register application with dashboard
client = DashboardClient(
    app_name="SynapticLlamas",
    router_type="RayHybridRouter",
    version="1.0.0",
    dashboard_url="http://localhost:8080",
    auto_register=True
)

# In dashboard command handler
if command == 'dashboard':
    dashboard = UnifiedDashboard(
        router=router,
        dashboard_port=8080
    )
    dashboard.run(allow_fallback=True)  # Graceful fallback
```

If another SOLLOL app (like a custom inference service) is already running with a dashboard, SynapticLlamas will detect it and share the same dashboard.

## Testing

### Test Script

```bash
# Start first app (SynapticLlamas)
cd ~/SynapticLlamas
python3 main.py --distributed
# Type: dashboard

# In another terminal, test fallback
cd ~/SOLLOL
python3 test_dashboard_fallback_simple.py
```

Expected output:
```
✅ Dashboard is already running on port 8080
Testing fallback behavior:
Attempting to start dashboard on port 8080 (already occupied)...
📊 Dashboard already running on port 8080
   Connecting to existing dashboard at http://localhost:8080
✅ Application will use shared dashboard for observability
```

## Troubleshooting

### Dashboard Not Accessible

**Issue**: Dashboard fallback detected but cannot access http://localhost:8080

**Solution**: Check if the first application's dashboard is actually running:
```bash
curl http://localhost:8080/api/health
```

### Port Conflicts

**Issue**: Want to run dashboards on different ports for different apps

**Solution**: Use custom ports for each application:
```python
# App 1
dashboard1 = UnifiedDashboard(router=router1, dashboard_port=8080)

# App 2
dashboard2 = UnifiedDashboard(router=router2, dashboard_port=8081)
```

### Disable Fallback

**Issue**: Need to ensure dashboard starts fresh each time

**Solution**: Disable fallback and handle errors manually:
```python
try:
    dashboard.run(allow_fallback=False)
except OSError as e:
    if "Address already in use" in str(e):
        # Kill existing process and retry
        subprocess.run(["pkill", "-f", "waitress"])
        dashboard.run(allow_fallback=False)
    else:
        raise
```

## Best Practices

1. **Enable Fallback by Default**: Use `allow_fallback=True` for production apps
2. **Single Dashboard Per Machine**: Let one "primary" app run the dashboard
3. **Dashboard Client Registration**: Register all apps with `DashboardClient` for visibility
4. **Health Checks**: Monitor `/api/health` endpoint for dashboard availability
5. **Graceful Shutdown**: Ensure dashboard cleanup on app exit

## API Reference

### UnifiedDashboard.run()

```python
def run(self, host: str = "0.0.0.0", debug: bool = False, allow_fallback: bool = True) -> None:
    """
    Run dashboard server (production-ready with Waitress).

    Args:
        host: Bind address (default: 0.0.0.0)
        debug: Enable Flask debug mode (default: False)
        allow_fallback: If True and port is in use, assume another dashboard is running (default: True)

    Raises:
        OSError: If port is in use and allow_fallback=False
    """
```

### Dashboard Endpoints

- `GET /` - Dashboard UI
- `GET /api/health` - Health check
- `GET /api/metrics` - Current metrics
- `GET /api/dashboard/config` - Dashboard configuration (Ray/Dask ports)
- `GET /api/applications` - Registered applications
- `GET /api/nodes` - Ollama pool nodes
- `GET /api/rpc_backends` - RPC backend status
- `WS /events` - Real-time event stream

## Version History

- **v0.9.16**: Added multi-app fallback with `allow_fallback` parameter
- **v0.9.15**: Added SOLLOL version logging
- **v0.9.14**: Ray OOM prevention
- **v0.9.13**: Fixed async/dict errors in metrics endpoint
- **v0.9.12**: Optimized panel sizing
- **v0.9.7**: Added dynamic port detection for Dask

## See Also

- [Unified Dashboard Documentation](UNIFIED_DASHBOARD.md)
- [Ray Integration Guide](RAY_INTEGRATION.md)
- [Dask Integration Guide](DASK_INTEGRATION.md)
- [Application Registration](DASHBOARD_CLIENT.md)
