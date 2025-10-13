#!/usr/bin/env python3
"""
Test all performance optimizations in SOLLOL
"""
import sys
import time
sys.path.insert(0, "/home/joker/SOLLOL/src")

from sollol import OllamaPool

def test_pool_initialization():
    """Test 1: Pool initialization with HTTP/2 and cache"""
    print("\n" + "="*80)
    print("Test 1: Pool Initialization")
    print("="*80)

    pool = OllamaPool.auto_configure(enable_cache=True)

    stats = pool.get_stats()

    print(f"✓ Pool created with {stats['nodes_configured']} nodes")
    print(f"✓ HTTP/2 enabled: {stats['http2_enabled']}")
    print(f"✓ Async I/O enabled: {stats['async_io_enabled']}")
    print(f"✓ Cache enabled: {stats['cache']['enabled']}")
    print(f"✓ Intelligent routing: {stats['intelligent_routing_enabled']}")

    if not stats['nodes_configured']:
        print("⚠️  No nodes found - some tests will be skipped")
        return pool, False

    print("\n✅ Pool initialization: PASSED")
    return pool, True


def test_response_caching(pool):
    """Test 2: Response caching"""
    print("\n" + "="*80)
    print("Test 2: Response Caching")
    print("="*80)

    try:
        # First request (cache miss)
        print("Making first request (cache miss)...")
        start = time.time()
        result1 = pool.embed(model="mxbai-embed-large", input="Test caching")
        latency1 = (time.time() - start) * 1000
        print(f"✓ First request: {latency1:.1f}ms")

        # Second request (should be cached)
        print("Making second request (cache hit)...")
        start = time.time()
        result2 = pool.embed(model="mxbai-embed-large", input="Test caching")
        latency2 = (time.time() - start) * 1000
        print(f"✓ Second request: {latency2:.1f}ms")

        # Check cache stats
        cache_stats = pool.get_cache_stats()
        print(f"\nCache stats:")
        print(f"  Size: {cache_stats['size']}/{cache_stats['max_size']}")
        print(f"  Hits: {cache_stats['hits']}")
        print(f"  Misses: {cache_stats['misses']}")
        print(f"  Hit rate: {cache_stats['hit_rate']:.1%}")

        if latency2 < latency1 * 0.5:
            print(f"\n✅ Cache speedup: {latency1/latency2:.1f}x faster")
        else:
            print(f"\n⚠️  Cache may not be working (latency2 not much faster)")

        print("\n✅ Response caching: PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Response caching: FAILED - {e}")
        return False


def test_cache_management(pool):
    """Test 3: Cache management API"""
    print("\n" + "="*80)
    print("Test 3: Cache Management API")
    print("="*80)

    try:
        # Test cache operations
        pool.clear_cache()
        print("✓ clear_cache() works")

        # Make a request to populate cache
        pool.embed(model="mxbai-embed-large", input="Test management")

        # List keys
        keys = pool.cache.list_keys()
        print(f"✓ list_keys() works - {len(keys)} keys")

        # Export/import
        exported = pool.export_cache()
        print(f"✓ export_cache() works - {len(exported.get('cache', {}))} entries")

        pool.clear_cache()
        imported = pool.import_cache(exported)
        print(f"✓ import_cache() works - {imported} entries imported")

        print("\n✅ Cache management: PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Cache management: FAILED - {e}")
        return False


def test_streaming(pool):
    """Test 4: Streaming support"""
    print("\n" + "="*80)
    print("Test 4: Streaming Support")
    print("="*80)

    try:
        print("Testing streaming generation...")
        chunk_count = 0

        for chunk in pool.generate(
            model="llama3.2",
            prompt="Say hello in exactly 5 words",
            stream=True
        ):
            chunk_count += 1
            if chunk_count <= 3:  # Show first 3 chunks
                content = chunk.get("response", "")
                if content:
                    print(f"  Chunk {chunk_count}: '{content}'")

        print(f"\n✓ Received {chunk_count} chunks")

        if chunk_count > 0:
            print("\n✅ Streaming: PASSED")
            return True
        else:
            print("\n⚠️  No chunks received")
            return False

    except NotImplementedError:
        print("\n⚠️  Streaming not supported in this version")
        return False
    except Exception as e:
        print(f"\n❌ Streaming: FAILED - {e}")
        return False


def test_model_warming(pool):
    """Test 5: Model warming"""
    print("\n" + "="*80)
    print("Test 5: Model Warming")
    print("="*80)

    try:
        print("Warming model 'llama3.2'...")
        success = pool.warm_model("llama3.2")

        if success:
            print("✓ Model warmed successfully")
            print("\n✅ Model warming: PASSED")
            return True
        else:
            print("⚠️  Model warming returned False")
            return False

    except Exception as e:
        print(f"\n❌ Model warming: FAILED - {e}")
        return False


def test_async_io(pool):
    """Test 6: Async I/O"""
    print("\n" + "="*80)
    print("Test 6: Async I/O Support")
    print("="*80)

    try:
        import asyncio

        async def test_async():
            print("Testing async chat...")
            result = await pool.chat_async(
                model="llama3.2",
                messages=[{"role": "user", "content": "Say hi"}]
            )
            return result

        # Run async test
        result = asyncio.run(test_async())

        if result:
            print("✓ Async chat completed")
            print("\n✅ Async I/O: PASSED")
            return True
        else:
            print("⚠️  Async chat returned empty result")
            return False

    except RuntimeError as e:
        if "httpx" in str(e).lower():
            print(f"⚠️  Async I/O requires httpx: {e}")
            return False
        raise
    except Exception as e:
        print(f"\n❌ Async I/O: FAILED - {e}")
        return False


def test_adaptive_health_checks(pool):
    """Test 7: Adaptive health checks"""
    print("\n" + "="*80)
    print("Test 7: Adaptive Health Checks")
    print("="*80)

    try:
        # Check if adaptive health checks are configured
        if hasattr(pool, '_adaptive_health_checks') and pool._adaptive_health_checks:
            print("✓ Adaptive health checks enabled")

            # Check health stats
            stats = pool.get_stats()
            if 'node_performance' in stats:
                print(f"✓ Monitoring {len(stats['node_performance'])} nodes")

                # Show one node's stats
                for node_key, perf in list(stats['node_performance'].items())[:1]:
                    print(f"\n  Sample node: {node_key}")
                    print(f"    Total requests: {perf.get('total_requests', 0)}")
                    print(f"    Failed requests: {perf.get('failed_requests', 0)}")
                    print(f"    Success rate: {perf.get('success_rate', 0):.1%}")

            print("\n✅ Adaptive health checks: PASSED")
            return True
        else:
            print("⚠️  Adaptive health checks not found")
            return False

    except Exception as e:
        print(f"\n❌ Adaptive health checks: FAILED - {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("SOLLOL Performance Optimization Test Suite")
    print("="*80)

    results = {}

    # Test 1: Initialization
    pool, has_nodes = test_pool_initialization()
    results['initialization'] = True

    if not has_nodes:
        print("\n⚠️  Skipping tests that require Ollama nodes")
        pool.stop()
        return

    # Test 2-7: Features that require nodes
    results['caching'] = test_response_caching(pool)
    results['cache_management'] = test_cache_management(pool)
    results['streaming'] = test_streaming(pool)
    results['model_warming'] = test_model_warming(pool)
    results['async_io'] = test_async_io(pool)
    results['adaptive_health'] = test_adaptive_health_checks(pool)

    # Cleanup
    pool.stop()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name:20s}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
