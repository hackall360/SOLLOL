#!/usr/bin/env python3
"""
Comparison: Basic HybridRouter vs Ray-Based HybridRouter

Shows the architectural difference between single-coordinator and
Ray-managed parallel coordinator pools.
"""

import asyncio
import logging

from sollol import HybridRouter, RayHybridRouter, OllamaPool

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def print_header(title: str):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def demo_basic_hybrid_router():
    """
    Basic HybridRouter - Single Coordinator

    Architecture:
    ┌─────────────┐
    │  Ollama Pool│  ← Small models (task distribution)
    └─────────────┘

    ┌─────────────────────────────────┐
    │   Single Coordinator (18080)    │  ← Large models
    │   ┌─────────┬─────────┐        │
    │   │ RPC #1  │ RPC #2  │        │
    │   └─────────┴─────────┘        │
    └─────────────────────────────────┘

    Limitations:
    - Only 1 coordinator serves requests
    - If coordinator busy, requests queue
    - No parallel sharding for high throughput
    """
    print_header("BASIC HYBRID ROUTER (Single Coordinator)")

    print("Configuration:")
    print("  • Ollama pool for small models (task distribution)")
    print("  • 1 coordinator with 2 RPC backends (model sharding)")
    print("  • Sequential request processing\n")

    # Example RPC backends (would be auto-discovered in production)
    rpc_backends = [
        {"host": "192.168.1.100", "port": 50052},
        {"host": "192.168.1.101", "port": 50052},
    ]

    router = HybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        rpc_backends=rpc_backends,
        coordinator_port=18080,
        enable_distributed=True
    )

    print("Routing behavior:")
    print("  llama3.2:3b  → Ollama pool (small model)")
    print("  llama3.1:70b → Single RPC coordinator (large model)")
    print("  llama3.1:405b → Single RPC coordinator (huge model)")

    print("\nRequest flow:")
    print("  Request 1 → Coordinator (port 18080)")
    print("  Request 2 → WAITS for coordinator to finish")
    print("  Request 3 → WAITS in queue")

    print("\n✅ Good for: 2-4 RPC backends, low concurrent load")
    print("❌ Not optimal for: High throughput, many concurrent requests")


async def demo_ray_hybrid_router():
    """
    Ray HybridRouter - Multiple Parallel Coordinators

    Architecture:
    ┌─────────────┐
    │  Ollama Pool│  ← Small models (task distribution)
    └─────────────┘

    ┌─────────────────────────────────────────────────────┐
    │              Ray Actor Pool System                  │
    │                                                     │
    │  ┌──────────────────┐    ┌──────────────────┐     │
    │  │  Pool 0 (18080)  │    │  Pool 1 (18081)  │     │
    │  │  ┌────┬────┐     │    │  ┌────┬────┐     │     │
    │  │  │RPC1│RPC2│     │    │  │RPC3│RPC4│     │     │
    │  │  └────┴────┘     │    │  └────┴────┘     │     │
    │  └──────────────────┘    └──────────────────┘     │
    │                                                     │
    │  Ray automatically:                                │
    │  • Picks least busy pool                          │
    │  • Queues requests if all busy                    │
    │  • Restarts failed pools                          │
    │  • Tracks resource usage                          │
    └─────────────────────────────────────────────────────┘

    Benefits:
    ✅ Parallel request processing (2x throughput with 2 pools)
    ✅ Automatic load balancing by Ray
    ✅ Fault tolerance with auto-restart
    ✅ Better GPU utilization
    """
    print_header("RAY HYBRID ROUTER (Multiple Parallel Coordinators)")

    print("Configuration:")
    print("  • Ollama pool for small models (task distribution)")
    print("  • 2 coordinator pools with 2 RPC backends each (parallel sharding)")
    print("  • Parallel request processing via Ray\n")

    # Example: 4 RPC backends split into 2 pools
    rpc_backends = [
        {"host": "192.168.1.100", "port": 50052},
        {"host": "192.168.1.101", "port": 50052},
        {"host": "192.168.1.102", "port": 50052},
        {"host": "192.168.1.103", "port": 50052},
    ]

    router = RayHybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        rpc_backends=rpc_backends,
        coordinator_base_port=18080,
        backends_per_pool=2,  # 2 backends per pool = 2 pools
        enable_distributed=True
    )

    print("Pool distribution:")
    print("  Pool 0 (port 18080): RPC backends 1, 2")
    print("  Pool 1 (port 18081): RPC backends 3, 4")

    print("\nRouting behavior:")
    print("  llama3.2:3b  → Ollama pool (small model)")
    print("  llama3.1:70b → Ray pool (Ray picks least busy)")
    print("  llama3.1:405b → Ray pool (Ray picks least busy)")

    print("\nRequest flow (parallel):")
    print("  Request 1 → Pool 0 (port 18080)")
    print("  Request 2 → Pool 1 (port 18081)  ← PARALLEL!")
    print("  Request 3 → Pool 0 (if free) or Pool 1 (if Pool 0 busy)")

    print("\n✅ Good for: 4+ RPC backends, high throughput needs")
    print("✅ Automatic: Load balancing, fault tolerance, resource tracking")

    # Show stats
    stats = router.get_stats()
    print("\nRay pool stats:")
    print(f"  Pools: {stats['ray_pools']['num_pools']}")
    print(f"  Backends per pool: {stats['ray_pools']['backends_per_pool']}")
    print(f"  Total backends: {stats['ray_pools']['total_backends']}")

    await router.shutdown()


async def demo_performance_comparison():
    """
    Performance comparison for concurrent requests.
    """
    print_header("PERFORMANCE COMPARISON (Concurrent Requests)")

    print("Scenario: 4 concurrent requests for llama3.1:70b\n")

    print("Basic HybridRouter (1 coordinator):")
    print("  ┌──────┐")
    print("  │ Req1 │ → Coordinator → Response (2s)")
    print("  └──────┘")
    print("         ┌──────┐")
    print("         │ Req2 │ → WAIT → Coordinator → Response (4s)")
    print("         └──────┘")
    print("                ┌──────┐")
    print("                │ Req3 │ → WAIT → Coordinator → Response (6s)")
    print("                └──────┘")
    print("                       ┌──────┐")
    print("                       │ Req4 │ → WAIT → Coordinator → Response (8s)")
    print("                       └──────┘")
    print("  Total time: ~8 seconds (sequential)")

    print("\nRay HybridRouter (2 pools):")
    print("  ┌──────┐")
    print("  │ Req1 │ → Pool 0 → Response (2s)")
    print("  └──────┘")
    print("  ┌──────┐")
    print("  │ Req2 │ → Pool 1 → Response (2s)  ← PARALLEL!")
    print("  └──────┘")
    print("         ┌──────┐")
    print("         │ Req3 │ → Pool 0 → Response (4s)")
    print("         └──────┘")
    print("         ┌──────┐")
    print("         │ Req4 │ → Pool 1 → Response (4s)  ← PARALLEL!")
    print("         └──────┘")
    print("  Total time: ~4 seconds (parallel)")

    print("\n🚀 Ray HybridRouter: 2x throughput with 2 pools!")
    print("🚀 With 4 pools: 4x throughput!")


async def main():
    """Run all demos."""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  SOLLOL: Basic HybridRouter vs Ray HybridRouter".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80)

    await demo_basic_hybrid_router()
    await demo_ray_hybrid_router()
    await demo_performance_comparison()

    print_header("RECOMMENDATION")

    print("Use Basic HybridRouter when:")
    print("  • You have 2-4 RPC backends")
    print("  • Low to moderate concurrent load")
    print("  • Simplicity is preferred")

    print("\nUse Ray HybridRouter when:")
    print("  • You have 4+ RPC backends")
    print("  • High concurrent load (multiple users)")
    print("  • Need maximum throughput")
    print("  • Want automatic fault tolerance")

    print("\n" + "=" * 80)
    print("✨ Ray HybridRouter is the future of SOLLOL distributed inference! ✨")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
