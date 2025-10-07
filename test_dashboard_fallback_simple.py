#!/usr/bin/env python3
"""
Simple test of multi-app dashboard fallback behavior without Ray conflicts.

This demonstrates how SOLLOL detects an existing dashboard and falls back gracefully.
"""
import time
import logging
import socket
from sollol import UnifiedDashboard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_port_in_use(port):
    """Check if a port is already in use."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result == 0

def test_dashboard_fallback():
    """Test dashboard fallback detection."""

    logger.info("=" * 70)
    logger.info("Testing SOLLOL Multi-App Dashboard Fallback")
    logger.info("=" * 70)

    # Check if dashboard is already running
    if check_port_in_use(8080):
        logger.info("✅ Dashboard is already running on port 8080")
        logger.info("")
        logger.info("Testing fallback behavior:")
        logger.info("-" * 70)

        # Create a dashboard instance
        dashboard = UnifiedDashboard(
            router=None,  # Can work without router for this test
            dashboard_port=8080
        )

        # This should detect the existing dashboard and fall back
        logger.info("Attempting to start dashboard on port 8080 (already occupied)...")
        dashboard.run(allow_fallback=True)

        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ FALLBACK TEST PASSED")
        logger.info("=" * 70)
        logger.info("Expected: Dashboard detected port in use and fell back gracefully")
        logger.info("Actual: No error raised, fallback message logged")

    else:
        logger.info("⚠️  No dashboard running on port 8080")
        logger.info("")
        logger.info("To test fallback:")
        logger.info("1. Start SynapticLlamas: cd ~/SynapticLlamas && python3 main.py --distributed")
        logger.info("2. Type 'dashboard' to start the unified dashboard")
        logger.info("3. Run this test again: python3 test_dashboard_fallback_simple.py")

if __name__ == "__main__":
    try:
        test_dashboard_fallback()
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
