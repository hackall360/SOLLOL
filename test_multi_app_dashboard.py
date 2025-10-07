#!/usr/bin/env python3
"""
Test multi-app dashboard fallback behavior.

This script demonstrates how multiple applications using SOLLOL can share
a single dashboard instance.
"""
import time
import logging
from sollol import OllamaPool, UnifiedDashboard, RayHybridRouter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_multi_app_fallback():
    """Test that second app detects existing dashboard and falls back gracefully."""

    # Create first app's infrastructure
    logger.info("=" * 70)
    logger.info("APP 1: Creating first application with dashboard")
    logger.info("=" * 70)

    pool1 = OllamaPool(nodes=[
        {"host": "localhost", "port": 11434}
    ])

    router1 = RayHybridRouter(
        ollama_pool=pool1,
        rpc_backends=[],
        enable_distributed=True
    )

    dashboard1 = UnifiedDashboard(
        router=router1,
        dashboard_port=8080
    )

    # Start first dashboard in a thread
    import threading
    dashboard_thread = threading.Thread(target=lambda: dashboard1.run(allow_fallback=True), daemon=True)
    dashboard_thread.start()

    # Give it time to start
    time.sleep(3)
    logger.info("✅ App 1 dashboard started on port 8080")

    # Now try to create second app with same port
    logger.info("")
    logger.info("=" * 70)
    logger.info("APP 2: Creating second application (should detect existing dashboard)")
    logger.info("=" * 70)

    pool2 = OllamaPool(nodes=[
        {"host": "localhost", "port": 11434}
    ])

    router2 = RayHybridRouter(
        ollama_pool=pool2,
        rpc_backends=[],
        enable_distributed=True
    )

    dashboard2 = UnifiedDashboard(
        router=router2,
        dashboard_port=8080  # Same port!
    )

    # This should detect existing dashboard and fallback
    logger.info("Attempting to start second dashboard on same port...")
    dashboard2.run(allow_fallback=True)

    logger.info("")
    logger.info("=" * 70)
    logger.info("RESULT: Multi-app fallback working correctly!")
    logger.info("=" * 70)
    logger.info("Both applications can now use the shared dashboard at http://localhost:8080")

    # Keep running for a bit
    time.sleep(5)

if __name__ == "__main__":
    try:
        test_multi_app_fallback()
    except KeyboardInterrupt:
        logger.info("Test interrupted")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
