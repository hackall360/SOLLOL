#!/usr/bin/env python3
"""
Test script to demonstrate full network discovery.

This will scan the entire subnet (10.9.66.0/24) and discover ALL Ollama nodes.
"""

import logging
import sys

# Add SOLLOL to path
sys.path.insert(0, '/home/joker/SOLLOL/src')

from sollol import OllamaPool

# Enable debug logging to see discovery progress
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 60)
    logger.info("Testing FULL NETWORK DISCOVERY (10.9.66.0/24)")
    logger.info("=" * 60)

    # Create pool with full network discovery
    logger.info("\n1. Creating OllamaPool with discover_all_nodes=True...")
    pool = OllamaPool.auto_configure(discover_all_nodes=True)

    logger.info(f"\n2. Discovery complete! Found {len(pool.nodes)} nodes:")
    for i, node in enumerate(pool.nodes, 1):
        logger.info(f"   {i}. {node['host']}:{node['port']}")

    # Show stats
    logger.info(f"\n3. Pool statistics:")
    logger.info(f"   - Total nodes: {len(pool.nodes)}")
    logger.info(f"   - Intelligent routing: {'enabled' if pool.enable_intelligent_routing else 'disabled'}")
    logger.info(f"   - VRAM monitoring: enabled ({pool.vram_monitor.gpu_type})")
    logger.info(f"   - VRAM buffer: {pool.VRAM_BUFFER_MB}MB")

    logger.info("\n" + "=" * 60)
    logger.info("Full network discovery test complete!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
