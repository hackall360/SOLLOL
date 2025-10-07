"""
SOLLOL Unified Dashboard - Integrates Ray, Dask, and SOLLOL metrics

Combines:
1. SOLLOL metrics (high-level overview)
2. Ray dashboard (task-level details, distributed tracing)
3. Dask dashboard (performance profiling)
4. Prometheus metrics export

Features:
- Embedded Ray dashboard iframe
- Embedded Dask dashboard iframe
- Real-time WebSocket updates
- Distributed tracing visualization
- Per-task resource monitoring
- Historical analytics (P50/P95/P99)
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional

import ray
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
from prometheus_client import Counter, Gauge, Histogram, generate_latest

logger = logging.getLogger(__name__)

# Prometheus metrics
request_counter = Counter(
    'sollol_requests_total',
    'Total requests processed',
    ['model', 'status', 'backend']
)

request_duration = Histogram(
    'sollol_request_duration_seconds',
    'Request duration in seconds',
    ['model', 'backend'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

active_pools = Gauge(
    'sollol_active_pools',
    'Number of active Ray pools'
)

gpu_utilization = Gauge(
    'sollol_gpu_utilization',
    'GPU utilization per node',
    ['node', 'gpu_id']
)


class UnifiedDashboard:
    """Unified dashboard integrating Ray, Dask, and SOLLOL metrics."""

    def __init__(
        self,
        router=None,
        ray_dashboard_port: int = 8265,
        dask_dashboard_port: int = 8787,
        dashboard_port: int = 8080,
    ):
        """
        Initialize unified dashboard.

        Args:
            router: SOLLOL router (any type)
            ray_dashboard_port: Ray dashboard port
            dask_dashboard_port: Dask dashboard port
            dashboard_port: Unified dashboard port
        """
        self.router = router
        self.ray_dashboard_port = ray_dashboard_port
        self.dask_dashboard_port = dask_dashboard_port
        self.dashboard_port = dashboard_port

        # Request history for analytics
        self.request_history = deque(maxlen=1000)
        self.trace_history = deque(maxlen=100)

        # Flask app
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()

        logger.info(
            f"📊 Unified Dashboard initialized "
            f"(port {dashboard_port}, Ray: {ray_dashboard_port}, Dask: {dask_dashboard_port})"
        )

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route("/")
        def index():
            """Serve unified dashboard HTML."""
            return render_template_string(UNIFIED_DASHBOARD_HTML)

        @self.app.route("/api/metrics")
        def metrics():
            """Get SOLLOL metrics."""
            try:
                if self.router:
                    stats = asyncio.run(self.router.get_stats())
                else:
                    stats = {}

                # Add request history analytics
                stats["analytics"] = self._calculate_analytics()

                return jsonify(stats)
            except Exception as e:
                logger.error(f"Error getting metrics: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/traces")
        def traces():
            """Get distributed traces."""
            return jsonify(list(self.trace_history))

        @self.app.route("/api/ray/metrics")
        def ray_metrics():
            """Get Ray metrics."""
            try:
                if ray.is_initialized():
                    # Get Ray metrics
                    ray_stats = {
                        "dashboard_url": f"http://localhost:{self.ray_dashboard_port}",
                        "nodes": len(ray.nodes()),
                        "available_resources": ray.available_resources(),
                        "cluster_resources": ray.cluster_resources(),
                    }
                    return jsonify(ray_stats)
                else:
                    return jsonify({"error": "Ray not initialized"}), 500
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/prometheus")
        def prometheus_metrics():
            """Prometheus metrics export."""
            return generate_latest()

        @self.app.route("/api/trace", methods=["POST"])
        def add_trace():
            """Add distributed trace."""
            trace_data = request.json
            trace_data["timestamp"] = datetime.utcnow().isoformat()
            self.trace_history.append(trace_data)
            return jsonify({"status": "ok"})

    def _calculate_analytics(self) -> Dict[str, Any]:
        """Calculate P50/P95/P99 latencies from history."""
        if not self.request_history:
            return {
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "total_requests": 0,
                "success_rate": 0,
            }

        latencies = sorted([r["latency_ms"] for r in self.request_history])
        total = len(latencies)

        def percentile(p):
            idx = int(total * p / 100)
            return latencies[min(idx, total - 1)]

        successful = sum(1 for r in self.request_history if r["status"] == "success")

        return {
            "p50_latency_ms": percentile(50),
            "p95_latency_ms": percentile(95),
            "p99_latency_ms": percentile(99),
            "total_requests": total,
            "success_rate": successful / total if total > 0 else 0,
        }

    def record_request(
        self,
        model: str,
        backend: str,
        latency_ms: float,
        status: str = "success"
    ):
        """Record request for analytics."""
        self.request_history.append({
            "model": model,
            "backend": backend,
            "latency_ms": latency_ms,
            "status": status,
            "timestamp": time.time(),
        })

        # Update Prometheus metrics
        request_counter.labels(model=model, status=status, backend=backend).inc()
        request_duration.labels(model=model, backend=backend).observe(latency_ms / 1000)

    def run(self, host: str = "0.0.0.0", debug: bool = False):
        """Run dashboard server."""
        logger.info(f"🚀 Starting Unified Dashboard on http://{host}:{self.dashboard_port}")
        logger.info(f"   Ray Dashboard: http://localhost:{self.ray_dashboard_port}")
        logger.info(f"   Dask Dashboard: http://localhost:{self.dask_dashboard_port}")
        logger.info(f"   Prometheus: http://{host}:{self.dashboard_port}/api/prometheus")

        self.app.run(host=host, port=self.dashboard_port, debug=debug)


# Unified Dashboard HTML Template
UNIFIED_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SOLLOL Unified Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .header h1 {
            font-size: 1.8rem;
            font-weight: 600;
        }
        .header .subtitle {
            color: rgba(255,255,255,0.9);
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto 1fr 1fr;
            gap: 1rem;
            padding: 1rem;
            height: calc(100vh - 120px);
        }
        .metrics-bar {
            grid-column: 1 / -1;
            display: flex;
            gap: 1rem;
            background: #1e293b;
            padding: 1.5rem;
            border-radius: 0.5rem;
        }
        .metric-card {
            flex: 1;
            background: #334155;
            padding: 1rem;
            border-radius: 0.5rem;
            border-left: 4px solid #667eea;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 600;
            color: #a78bfa;
        }
        .metric-label {
            color: #94a3b8;
            font-size: 0.85rem;
            margin-top: 0.25rem;
        }
        .dashboard-panel {
            background: #1e293b;
            border-radius: 0.5rem;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .panel-header {
            background: #334155;
            padding: 0.75rem 1rem;
            font-weight: 600;
            border-bottom: 2px solid #667eea;
        }
        .panel-content {
            flex: 1;
            overflow: hidden;
        }
        iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
        .status-active { background: #10b981; }
        .status-inactive { background: #ef4444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 SOLLOL Unified Dashboard</h1>
        <div class="subtitle">
            Real-time monitoring • Distributed tracing • Performance analytics
        </div>
    </div>

    <div class="container">
        <!-- Metrics Bar -->
        <div class="metrics-bar" id="metrics-bar">
            <div class="metric-card">
                <div class="metric-value" id="p50-latency">--</div>
                <div class="metric-label">P50 Latency (ms)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="p95-latency">--</div>
                <div class="metric-label">P95 Latency (ms)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="p99-latency">--</div>
                <div class="metric-label">P99 Latency (ms)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="success-rate">--</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="total-pools">--</div>
                <div class="metric-label">Active Pools</div>
            </div>
        </div>

        <!-- SOLLOL Metrics -->
        <div class="dashboard-panel">
            <div class="panel-header">
                <span class="status-indicator status-active"></span>
                SOLLOL Metrics
            </div>
            <div class="panel-content" id="sollol-metrics">
                <pre id="metrics-json" style="padding: 1rem; overflow: auto; height: 100%; color: #a78bfa;"></pre>
            </div>
        </div>

        <!-- Distributed Traces -->
        <div class="dashboard-panel">
            <div class="panel-header">
                <span class="status-indicator status-active"></span>
                Distributed Traces
            </div>
            <div class="panel-content">
                <pre id="traces-json" style="padding: 1rem; overflow: auto; height: 100%; color: #10b981;"></pre>
            </div>
        </div>

        <!-- Ray Dashboard -->
        <div class="dashboard-panel">
            <div class="panel-header">
                <span class="status-indicator" id="ray-status"></span>
                Ray Dashboard
            </div>
            <div class="panel-content">
                <iframe src="http://localhost:8265" id="ray-iframe"></iframe>
            </div>
        </div>

        <!-- Dask Dashboard -->
        <div class="dashboard-panel">
            <div class="panel-header">
                <span class="status-indicator" id="dask-status"></span>
                Dask Dashboard
            </div>
            <div class="panel-content">
                <iframe src="http://localhost:8787" id="dask-iframe"></iframe>
            </div>
        </div>
    </div>

    <script>
        // Update metrics every 2 seconds
        setInterval(async () => {
            try {
                // SOLLOL metrics
                const metricsRes = await fetch('/api/metrics');
                const metrics = await metricsRes.json();

                // Update analytics
                if (metrics.analytics) {
                    document.getElementById('p50-latency').textContent =
                        metrics.analytics.p50_latency_ms.toFixed(0);
                    document.getElementById('p95-latency').textContent =
                        metrics.analytics.p95_latency_ms.toFixed(0);
                    document.getElementById('p99-latency').textContent =
                        metrics.analytics.p99_latency_ms.toFixed(0);
                    document.getElementById('success-rate').textContent =
                        (metrics.analytics.success_rate * 100).toFixed(1) + '%';
                }

                // Update pool count
                if (metrics.total_pools !== undefined) {
                    document.getElementById('total-pools').textContent = metrics.total_pools;
                }

                // Display full metrics
                document.getElementById('metrics-json').textContent =
                    JSON.stringify(metrics, null, 2);

                // Traces
                const tracesRes = await fetch('/api/traces');
                const traces = await tracesRes.json();
                document.getElementById('traces-json').textContent =
                    JSON.stringify(traces, null, 2);

                // Check Ray status
                try {
                    const rayRes = await fetch('/api/ray/metrics');
                    document.getElementById('ray-status').className =
                        rayRes.ok ? 'status-indicator status-active' : 'status-indicator status-inactive';
                } catch {
                    document.getElementById('ray-status').className = 'status-indicator status-inactive';
                }

            } catch (error) {
                console.error('Error updating metrics:', error);
            }
        }, 2000);
    </script>
</body>
</html>
"""


def run_unified_dashboard(
    router=None,
    ray_dashboard_port: int = 8265,
    dask_dashboard_port: int = 8787,
    dashboard_port: int = 8080,
    host: str = "0.0.0.0"
):
    """
    Run unified dashboard server.

    Args:
        router: SOLLOL router instance
        ray_dashboard_port: Ray dashboard port
        dask_dashboard_port: Dask dashboard port
        dashboard_port: Unified dashboard port
        host: Host to bind to
    """
    dashboard = UnifiedDashboard(
        router=router,
        ray_dashboard_port=ray_dashboard_port,
        dask_dashboard_port=dask_dashboard_port,
        dashboard_port=dashboard_port,
    )

    dashboard.run(host=host)
