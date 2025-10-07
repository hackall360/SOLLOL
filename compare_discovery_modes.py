#!/usr/bin/env python3
"""
Compare fast discovery vs full network discovery.

Shows the difference between:
1. Fast mode (default) - returns as soon as it finds one node
2. Full mode - scans entire subnet and returns ALL nodes
"""

import logging
import sys
import time

# Add SOLLOL to path
sys.path.insert(0, '/home/joker/SOLLOL/src')

from sollol import OllamaPool

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 80)
    logger.info("SOLLOL DISCOVERY MODE COMPARISON")
    logger.info("=" * 80)

    # Test 1: Fast discovery (default)
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Fast Discovery (default - returns first node found)")
    logger.info("=" * 80)
    start = time.time()
    pool_fast = OllamaPool.auto_configure(discover_all_nodes=False)
    fast_time = time.time() - start

    logger.info(f"\nFast discovery results:")
    logger.info(f"  - Nodes found: {len(pool_fast.nodes)}")
    logger.info(f"  - Time taken: {fast_time:.2f} seconds")
    for i, node in enumerate(pool_fast.nodes, 1):
        logger.info(f"  - Node {i}: {node['host']}:{node['port']}")

    # Test 2: Full network discovery
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Full Network Discovery (scans entire 10.9.66.0/24 subnet)")
    logger.info("=" * 80)
    start = time.time()
    pool_full = OllamaPool.auto_configure(discover_all_nodes=True)
    full_time = time.time() - start

    logger.info(f"\nFull network discovery results:")
    logger.info(f"  - Nodes found: {len(pool_full.nodes)}")
    logger.info(f"  - Time taken: {full_time:.2f} seconds")
    for i, node in enumerate(pool_full.nodes, 1):
        logger.info(f"  - Node {i}: {node['host']}:{node['port']}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Fast mode: {len(pool_fast.nodes)} nodes in {fast_time:.2f}s")
    logger.info(f"Full mode: {len(pool_full.nodes)} nodes in {full_time:.2f}s")
    logger.info(f"\nAdditional nodes discovered in full mode: {len(pool_full.nodes) - len(pool_fast.nodes)}")

    if len(pool_full.nodes) > len(pool_fast.nodes):
        logger.info("\n✅ Full network discovery found MORE nodes!")
        logger.info("   Use discover_all_nodes=True when you need comprehensive discovery.")
    else:
        logger.info("\n⚠️  Both modes found the same number of nodes.")
        logger.info("   Fast mode is sufficient for this network.")

    logger.info("\n" + "=" * 80)

if __name__ == "__main__":
    main()
