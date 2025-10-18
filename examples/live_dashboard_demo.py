#!/usr/bin/env python3
"""
SOLLOL Unified Dashboard - Live Demo

Demonstrates the NEW universal dashboard features:
- Network-wide observability (all Ollama nodes + RPC backends)
- Application tracking (see which apps are using SOLLOL)
- Real-time WebSocket event streams
- Ray + Dask dashboard integration
"""

import asyncio
import logging
import threading
import time

from sollol import (
    UnifiedDashboard,
    RayAdvancedRouter,
    OllamaPool,
    DashboardClient,
    get_tracer,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def simulate_requests(router, dashboard):
    """Simulate some requests to generate dashboard activity."""
    tracer = get_tracer(dashboard=dashboard)

    logger.info("🔄 Simulating requests to generate dashboard activity...\n")

    test_requests = [
        ("llama3.2:3b", "What is 2+2?"),
        ("llama3.2:3b", "Explain machine learning briefly"),
    ]

    summary = {
        "requests_attempted": len(test_requests),
        "requests_succeeded": 0,
        "requests_failed": 0,
    }

    for i, (model, prompt) in enumerate(test_requests, 1):
        try:
            trace_span = tracer.start_trace(
                operation="chat",
                backend="ollama",
                model=model,
                request_id=f"demo-req-{i}"
            )

            start_time = time.time()

            response = await router.route_request(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )

            latency_ms = (time.time() - start_time) * 1000

            tracer.end_span(
                trace_span,
                status="success",
                latency_ms=latency_ms,
                response_length=len(response['message']['content'])
            )

            dashboard.record_request(
                model=model,
                backend="ollama",
                latency_ms=latency_ms,
                status="success"
            )

            logger.info(f"✅ Request {i}: {prompt[:30]}... ({latency_ms:.0f}ms)")
            summary["requests_succeeded"] += 1
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ Request {i} failed: {e}")
            summary["requests_failed"] += 1

    return summary

async def run_demo(*, run_duration: float | None = None, heartbeat_interval: float = 10.0):
    """Run the live dashboard demo and return a summary dictionary."""

    summary: dict[str, float | int] = {
        "requests_attempted": 0,
        "requests_succeeded": 0,
        "requests_failed": 0,
        "uptime_seconds": 0.0,
    }

    start_time = time.time()
    print("=" * 80)
    print("  🚀 SOLLOL Universal Dashboard - Live Demo")
    print("=" * 80)
    print()

    # Step 1: Register this demo app with the dashboard
    print("1️⃣  Registering demo application with dashboard...")
    client = DashboardClient(
        app_name="Dashboard Demo",
        router_type="RayAdvancedRouter",
        version="demo",
        dashboard_url="http://localhost:8080",
        metadata={"environment": "demo", "purpose": "showcase"},
    )
    print("   ✅ Application registered\n")

    # Step 2: Create SOLLOL router
    print("2️⃣  Creating RayAdvancedRouter...")
    router = RayAdvancedRouter(
        ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
        enable_batching=False,
        enable_speculation=False,
        auto_discover_rpc=False,
    )
    print("   ✅ Router initialized\n")

    # Step 3: Create unified dashboard
    print("3️⃣  Creating Unified Dashboard with NEW features...")
    dashboard = UnifiedDashboard(
        router=router,
        ray_dashboard_port=8265,
        dask_dashboard_port=8787,
        dashboard_port=8080,
        enable_dask=True,  # Enable Dask dashboard
    )
    print("   ✅ Dashboard created\n")

    # Step 4: Start dashboard in background
    print("4️⃣  Starting dashboard server...")
    dashboard_thread = threading.Thread(
        target=dashboard.run,
        kwargs={"host": "0.0.0.0", "debug": False},
        daemon=True
    )
    dashboard_thread.start()
    await asyncio.sleep(2)  # Let dashboard start
    print("   ✅ Dashboard running\n")

    # Display access information
    print("=" * 80)
    print("  📊 DASHBOARD ACCESS")
    print("=" * 80)
    print()
    print("🌐 Web UI:")
    print("   http://localhost:8080")
    print()
    print("📊 NEW Features Visible in Dashboard:")
    print("   • Applications panel - see this demo app listed!")
    print("   • Network nodes - all discovered Ollama nodes")
    print("   • RPC backends - all llama.cpp backends")
    print("   • Ray dashboard (embedded) - http://localhost:8265")
    print("   • Dask dashboard (embedded) - http://localhost:8787")
    print()
    print("🔌 NEW API Endpoints:")
    print("   GET  /api/applications - List all apps using SOLLOL")
    print("   GET  /api/network/nodes - All Ollama nodes (router-agnostic)")
    print("   GET  /api/network/backends - All RPC backends")
    print("   GET  /api/network/health - Network health summary")
    print()
    print("📡 NEW WebSocket Streams:")
    print("   ws://localhost:8080/ws/applications - App lifecycle events")
    print("   ws://localhost:8080/ws/network/nodes - Node state changes")
    print("   ws://localhost:8080/ws/network/backends - Backend events")
    print("   ws://localhost:8080/ws/ollama_activity - Model load/unload/processing")
    print()
    print("=" * 80)
    print()

    # Step 5: Generate some activity
    print("5️⃣  Generating dashboard activity...")
    print()
    request_summary = await simulate_requests(router, dashboard)
    summary.update(request_summary)
    print()

    # Keep running
    print("=" * 80)
    print("  ✨ Dashboard Running - Press Ctrl+C to exit")
    print("=" * 80)
    print()
    print("💡 Open http://localhost:8080 in your browser to see:")
    print("   1. This application listed in the 'Applications' panel")
    print("   2. All Ollama nodes in your network")
    print("   3. Request metrics and traces")
    print("   4. Embedded Ray and Dask dashboards")
    print()
    print("   The 'Applications' panel shows which apps are using SOLLOL!")
    print("   This is the NEW universal observability feature.")
    print()

    deadline = time.monotonic() + run_duration if run_duration is not None else None
    try:
        while True:
            await asyncio.sleep(heartbeat_interval)
            logger.info("📊 Dashboard still running... (this app is visible in /api/applications)")
            if deadline is not None and time.monotonic() >= deadline:
                logger.info("⏱️ Run duration reached; preparing to shut down.")
                break
    except KeyboardInterrupt:
        logger.info("🔻 Interrupt received; shutting down demo.")

    print("\n\n🛑 Shutting down...")
    client.unregister()
    await router.shutdown()
    print("✅ Shutdown complete!")

    summary["uptime_seconds"] = time.time() - start_time
    print("\nSummary:")
    print(
        "  Requests: "
        f"{summary['requests_succeeded']}/{summary['requests_attempted']} succeeded"
    )
    print(f"  Failures: {summary['requests_failed']}")
    print(f"  Uptime  : {summary['uptime_seconds']:.1f}s")

    return summary


if __name__ == "__main__":
    asyncio.run(run_demo())
