#!/usr/bin/env python3
"""
Test Ray advanced features to ensure they work correctly.
"""

import asyncio
import logging
import sys

sys.path.insert(0, '/home/joker/SOLLOL/src')

from sollol import RayAdvancedRouter, OllamaPool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_initialization():
    """Test 1: Basic router initialization."""
    logger.info("=" * 80)
    logger.info("TEST 1: Basic Initialization")
    logger.info("=" * 80)

    try:
        router = RayAdvancedRouter(
            ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
            auto_discover_rpc=True,
            enable_batching=True,
            enable_speculation=True,
        )

        stats = await router.get_stats()
        logger.info(f"\n✅ Router initialized successfully!")
        logger.info(f"   Router type: {stats['router_type']}")
        logger.info(f"   Batching: {stats['features']['batching']}")
        logger.info(f"   Speculation: {stats['features']['speculation']}")
        logger.info(f"   Ollama nodes: {stats['ollama_pool']['nodes']}")
        logger.info(f"   Total warm pools: {stats['total_pools']}")

        await router.shutdown()
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_ollama_routing():
    """Test 2: Routing to Ollama for small models."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Ollama Routing (Small Models)")
    logger.info("=" * 80)

    try:
        router = RayAdvancedRouter(
            ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
            auto_discover_rpc=True,
        )

        # Test with small model (should go to Ollama)
        logger.info("\nSending request to llama3.2:3b (should route to Ollama)...")

        response = await router.route_request(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": "What is 2+2?"}]
        )

        logger.info(f"✅ Response received!")
        logger.info(f"   Response preview: {response['message']['content'][:100]}...")

        await router.shutdown()
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_vram_aware_routing():
    """Test 3: VRAM-aware routing logic."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: VRAM-Aware Routing Logic")
    logger.info("=" * 80)

    try:
        router = RayAdvancedRouter(
            ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
            model_vram_threshold_mb=16384,  # 16GB threshold
            auto_discover_rpc=True,
        )

        test_cases = [
            ("llama3.2:1b", False),   # 1B params, ~2GB → Ollama
            ("llama3.2:3b", False),   # 3B params, ~6GB → Ollama
            ("llama3.1:8b", False),   # 8B params, ~16GB → Ollama (at threshold)
            ("llama3.1:70b", True),   # 70B params, ~140GB → RPC
            ("llama3.1:405b", True),  # 405B params, ~810GB → RPC
        ]

        logger.info("\nTesting routing decisions:")
        all_correct = True

        for model, expected_rpc in test_cases:
            should_use_rpc = router._should_use_rpc(model)
            route = "RPC" if should_use_rpc else "Ollama"
            expected_route = "RPC" if expected_rpc else "Ollama"

            match = "✅" if should_use_rpc == expected_rpc else "❌"
            logger.info(f"   {match} {model:<20} → {route:<10} (expected: {expected_route})")

            if should_use_rpc != expected_rpc:
                all_correct = False

        await router.shutdown()

        if all_correct:
            logger.info("\n✅ All routing decisions correct!")
            return True
        else:
            logger.error("\n❌ Some routing decisions incorrect!")
            return False

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_concurrent_requests():
    """Test 4: Concurrent request handling."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Concurrent Request Handling")
    logger.info("=" * 80)

    try:
        router = RayAdvancedRouter(
            ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
            auto_discover_rpc=True,
        )

        logger.info("\nSending 3 concurrent requests to llama3.2:3b...")

        tasks = [
            router.route_request(
                model="llama3.2:3b",
                messages=[{"role": "user", "content": f"What is {i} + {i}?"}]
            )
            for i in range(1, 4)
        ]

        responses = await asyncio.gather(*tasks)

        logger.info(f"✅ All {len(responses)} requests completed!")
        for i, response in enumerate(responses, 1):
            preview = response['message']['content'][:60]
            logger.info(f"   Response {i}: {preview}...")

        await router.shutdown()
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_stats():
    """Test 5: Statistics reporting."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Statistics Reporting")
    logger.info("=" * 80)

    try:
        router = RayAdvancedRouter(
            ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
            enable_batching=True,
            enable_speculation=True,
            auto_discover_rpc=True,
        )

        stats = await router.get_stats()

        logger.info("\nRouter Statistics:")
        logger.info(f"   Router type: {stats['router_type']}")
        logger.info(f"   Features:")
        logger.info(f"      Warm pools: {stats['features']['warm_pools']}")
        logger.info(f"      Batching: {stats['features']['batching']}")
        logger.info(f"      Speculation: {stats['features']['speculation']}")
        logger.info(f"   Ollama pool nodes: {stats['ollama_pool']['nodes']}")
        logger.info(f"   Total warm pools: {stats['total_pools']}")

        logger.info("\n✅ Statistics retrieved successfully!")

        await router.shutdown()
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all tests."""
    logger.info("\n" + "█" * 80)
    logger.info("█" + " " * 78 + "█")
    logger.info("█" + "  SOLLOL Ray Advanced Features - Test Suite".center(78) + "█")
    logger.info("█" + " " * 78 + "█")
    logger.info("█" * 80)

    tests = [
        ("Basic Initialization", test_basic_initialization),
        ("Ollama Routing", test_ollama_routing),
        ("VRAM-Aware Routing", test_vram_aware_routing),
        ("Concurrent Requests", test_concurrent_requests),
        ("Statistics Reporting", test_stats),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}", exc_info=True)
            results.append((name, False))

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"   {status}: {name}")

    logger.info(f"\n   Total: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 All tests passed! Ray features working correctly!")
    else:
        logger.error(f"\n⚠️  {total - passed} test(s) failed!")

    logger.info("=" * 80 + "\n")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
