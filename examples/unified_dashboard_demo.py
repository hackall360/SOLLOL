#!/usr/bin/env python3
"""
SOLLOL Unified Dashboard Demo

Demonstrates the integrated monitoring dashboard with:
1. Ray dashboard (task timeline, distributed tracing)
2. Dask dashboard (performance profiling)
3. SOLLOL metrics (high-level overview)
4. Prometheus export
5. Real-time distributed tracing

Access dashboards at:
- Unified: http://localhost:8080
- Ray: http://localhost:8265
- Dask: http://localhost:8787
- Prometheus: http://localhost:8080/api/prometheus
"""

import asyncio
import logging
import threading
import time

from sollol import (
    RayAdvancedRouter,
    OllamaPool,
    UnifiedDashboard,
    get_tracer,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_sample_requests(router, dashboard):
    """Run sample requests to generate dashboard data."""
    tracer = get_tracer(dashboard=dashboard)

    test_requests = [
        ("llama3.2:3b", "What is 2+2?"),
        ("llama3.2:3b", "What is the capital of France?"),
        ("llama3.2:3b", "Explain photosynthesis briefly."),
    ]

    logger.info("🚀 Sending sample requests to generate dashboard data...\n")

    for i, (model, prompt) in enumerate(test_requests, 1):
        try:
            # Start trace
            trace_span = tracer.start_trace(
                operation="chat",
                backend="ollama",
                model=model,
                request_id=f"req-{i}"
            )

            start_time = time.time()

            # Make request
            response = await router.route_request(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )

            latency_ms = (time.time() - start_time) * 1000

            # End trace
            tracer.end_span(
                trace_span,
                status="success",
                latency_ms=latency_ms,
                response_length=len(response['message']['content'])
            )

            # Record in dashboard
            dashboard.record_request(
                model=model,
                backend="ollama",
                latency_ms=latency_ms,
                status="success"
            )

            logger.info(f"✅ Request {i} completed ({latency_ms:.0f}ms)")
            logger.info(f"   Prompt: {prompt}")
            logger.info(f"   Response: {response['message']['content'][:80]}...\n")

            await asyncio.sleep(2)  # Pause between requests

        except Exception as e:
            logger.error(f"❌ Request {i} failed: {e}\n")

            # Record failure
            tracer.end_span(trace_span, status="error", error=str(e))
            dashboard.record_request(
                model=model,
                backend="error",
                latency_ms=0,
                status="error"
            )


async def main():
    """Main demo function."""
    logger.info("=" * 80)
    logger.info("  SOLLOL Unified Dashboard Demo")
    logger.info("=" * 80 + "\n")

    # Create router
    logger.info("📡 Initializing RayAdvancedRouter...\n")
    router = RayAdvancedRouter(
        ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
        enable_batching=True,
        enable_speculation=False,  # Disable for cleaner demo
        auto_discover_rpc=True,
    )

    # Create unified dashboard
    logger.info("📊 Creating Unified Dashboard...\n")
    dashboard = UnifiedDashboard(
        router=router,
        ray_dashboard_port=8265,
        dask_dashboard_port=8787,
        dashboard_port=8080,
    )

    # Start dashboard in background thread
    dashboard_thread = threading.Thread(
        target=dashboard.run,
        kwargs={"host": "0.0.0.0", "debug": False},
        daemon=True
    )
    dashboard_thread.start()

    logger.info("✅ Dashboard started!\n")
    logger.info("🌐 Access dashboards at:\n")
    logger.info("   📊 Unified Dashboard:  http://localhost:8080")
    logger.info("   📈 Ray Dashboard:      http://localhost:8265")
    logger.info("   📉 Dask Dashboard:     http://localhost:8787")
    logger.info("   📉 Prometheus Metrics: http://localhost:8080/api/prometheus")
    logger.info("\n" + "=" * 80 + "\n")

    # Wait for dashboard to start
    await asyncio.sleep(2)

    # Run sample requests
    await run_sample_requests(router, dashboard)

    # Keep running to allow dashboard exploration
    logger.info("=" * 80)
    logger.info("  Dashboard Running - Press Ctrl+C to exit")
    logger.info("=" * 80 + "\n")

    logger.info("💡 Explore the unified dashboard at http://localhost:8080\n")
    logger.info("   You'll see:")
    logger.info("   • P50/P95/P99 latency metrics")
    logger.info("   • Success rate and active pools")
    logger.info("   • Distributed traces with timing")
    logger.info("   • Embedded Ray dashboard (task timeline)")
    logger.info("   • Embedded Dask dashboard (performance profiling)")
    logger.info("   • Prometheus metrics export\n")

    try:
        while True:
            await asyncio.sleep(60)
            logger.info("📊 Dashboard still running... (Press Ctrl+C to exit)")
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Shutting down...")
        await router.shutdown()
        logger.info("✅ Shutdown complete!")


if __name__ == "__main__":
    asyncio.run(main())
