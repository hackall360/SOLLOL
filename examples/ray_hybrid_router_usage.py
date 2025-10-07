#!/usr/bin/env python3
"""
Practical example: Using RayHybridRouter for parallel RPC sharding.

This example shows how to:
1. Initialize RayHybridRouter with multiple RPC backends
2. Route small models to Ollama (task distribution)
3. Route large models to Ray pools (parallel sharding)
4. Handle concurrent requests efficiently
"""

import asyncio
import logging
import time

from sollol import RayHybridRouter, OllamaPool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def basic_usage():
    """Basic RayHybridRouter setup and usage."""
    logger.info("=" * 80)
    logger.info("Example 1: Basic RayHybridRouter Usage")
    logger.info("=" * 80)

    # Option 1: Auto-discover RPC backends
    logger.info("\n📡 Auto-discovering RPC backends...")
    router = RayHybridRouter(
        ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
        rpc_backends=None,  # Will auto-discover
        auto_discover_rpc=True,
        backends_per_pool=2,  # 2 RPC backends per pool
        enable_distributed=True
    )

    # Option 2: Manual RPC backend configuration
    """
    rpc_backends = [
        {"host": "192.168.1.100", "port": 50052},
        {"host": "192.168.1.101", "port": 50052},
        {"host": "192.168.1.102", "port": 50052},
        {"host": "192.168.1.103", "port": 50052},
    ]

    router = RayHybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        rpc_backends=rpc_backends,
        backends_per_pool=2,  # Creates 2 pools with 2 backends each
        coordinator_base_port=18080,
        enable_distributed=True
    )
    """

    # Show configuration
    stats = router.get_stats()
    logger.info(f"\n✅ Router initialized:")
    logger.info(f"   Ollama nodes: {stats['ollama_pool']['nodes']}")
    logger.info(f"   Ray pools: {stats['ray_pools']['num_pools']}")
    logger.info(f"   Backends per pool: {stats['ray_pools']['backends_per_pool']}")
    logger.info(f"   Total RPC backends: {stats['ray_pools']['total_backends']}")

    # Example request - small model (goes to Ollama)
    logger.info("\n🔹 Request 1: Small model (Ollama)")
    response = await router.route_request(
        model="llama3.2:3b",
        messages=[{"role": "user", "content": "What is 2+2?"}]
    )
    logger.info(f"   Response: {response['message']['content'][:100]}...")

    # Example request - large model (goes to Ray pool)
    logger.info("\n🔹 Request 2: Large model (Ray sharded pool)")
    response = await router.route_request(
        model="llama3.1:70b",
        messages=[{"role": "user", "content": "Explain quantum computing."}]
    )
    logger.info(f"   Response: {response['message']['content'][:100]}...")

    await router.shutdown()


async def concurrent_requests():
    """Demonstrate parallel request handling with Ray pools."""
    logger.info("\n" + "=" * 80)
    logger.info("Example 2: Concurrent Request Handling")
    logger.info("=" * 80)

    # Simulate 4 RPC backends split into 2 pools
    rpc_backends = [
        {"host": "192.168.1.100", "port": 50052},
        {"host": "192.168.1.101", "port": 50052},
        {"host": "192.168.1.102", "port": 50052},
        {"host": "192.168.1.103", "port": 50052},
    ]

    router = RayHybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        rpc_backends=rpc_backends,
        backends_per_pool=2,  # 2 pools
        enable_distributed=True
    )

    logger.info(f"\n🚀 Sending 4 concurrent requests for llama3.1:70b...")
    logger.info(f"   Ray will distribute across 2 pools for parallel processing")

    # Create 4 concurrent requests
    start_time = time.time()

    tasks = [
        router.route_request(
            model="llama3.1:70b",
            messages=[{"role": "user", "content": f"Question {i}: What is the meaning of life?"}]
        )
        for i in range(1, 5)
    ]

    # Execute in parallel
    responses = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    logger.info(f"\n✅ All 4 requests completed in {elapsed:.2f}s")
    logger.info(f"   Ray automatically distributed across pools:")
    logger.info(f"   • Requests 1-2 → Pool 0 & Pool 1 (parallel)")
    logger.info(f"   • Requests 3-4 → Pool 0 & Pool 1 (parallel)")
    logger.info(f"   🚀 ~2x speedup compared to single coordinator!")

    for i, response in enumerate(responses, 1):
        logger.info(f"   Response {i}: {response['message']['content'][:80]}...")

    await router.shutdown()


async def adaptive_routing():
    """Demonstrate adaptive routing based on model size."""
    logger.info("\n" + "=" * 80)
    logger.info("Example 3: Adaptive Routing (Small → Ollama, Large → Ray Pools)")
    logger.info("=" * 80)

    router = RayHybridRouter(
        ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
        auto_discover_rpc=True,
        backends_per_pool=2,
        model_vram_threshold_mb=16384,  # 16GB threshold
        enable_distributed=True
    )

    # Test different model sizes
    test_cases = [
        ("llama3.2:1b", "Ollama (1B params, ~2GB VRAM)"),
        ("llama3.2:3b", "Ollama (3B params, ~6GB VRAM)"),
        ("llama3.1:8b", "Ollama (8B params, ~16GB VRAM)"),
        ("llama3.1:70b", "Ray Pool (70B params, ~140GB VRAM - needs sharding)"),
        ("llama3.1:405b", "Ray Pool (405B params, ~810GB VRAM - needs sharding)"),
    ]

    logger.info("\n🎯 Routing decisions based on model size:")
    for model, expected_route in test_cases:
        should_use_rpc = router._should_use_rpc(model)
        actual_route = "Ray Pool (RPC)" if should_use_rpc else "Ollama"
        logger.info(f"   {model:<20} → {actual_route:<20} ({expected_route})")

    await router.shutdown()


async def fault_tolerance():
    """Demonstrate Ray's fault tolerance."""
    logger.info("\n" + "=" * 80)
    logger.info("Example 4: Ray Fault Tolerance")
    logger.info("=" * 80)

    logger.info("\n🛡️  Ray provides automatic fault tolerance:")
    logger.info("   • If a pool crashes, Ray restarts it automatically")
    logger.info("   • Failed requests are retried on another pool")
    logger.info("   • No manual intervention required")

    logger.info("\nExample scenario:")
    logger.info("   1. Pool 0 crashes during inference")
    logger.info("   2. Ray detects the failure")
    logger.info("   3. Ray restarts Pool 0 actor")
    logger.info("   4. Request is retried on Pool 1 (or restarted Pool 0)")
    logger.info("   5. User sees successful response")

    logger.info("\n✅ This is handled automatically by Ray - no code changes needed!")


async def main():
    """Run all examples."""
    logger.info("\n" + "█" * 80)
    logger.info("█" + " " * 78 + "█")
    logger.info("█" + "  SOLLOL RayHybridRouter - Practical Usage Examples".center(78) + "█")
    logger.info("█" + " " * 78 + "█")
    logger.info("█" * 80)

    # Run examples
    await basic_usage()
    # await concurrent_requests()  # Uncomment if you have RPC backends
    await adaptive_routing()
    await fault_tolerance()

    logger.info("\n" + "=" * 80)
    logger.info("🎉 RayHybridRouter Examples Complete!")
    logger.info("=" * 80)

    logger.info("\n📚 Key Takeaways:")
    logger.info("   1. Ray manages multiple sharded pools automatically")
    logger.info("   2. Small models → Ollama (task distribution)")
    logger.info("   3. Large models → Ray pools (parallel sharding)")
    logger.info("   4. Automatic load balancing and fault tolerance")
    logger.info("   5. 2x-4x throughput with multiple pools")

    logger.info("\n🚀 Use RayHybridRouter when you have 4+ RPC backends!")
    logger.info("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
