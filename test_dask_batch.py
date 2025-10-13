#!/usr/bin/env python3
"""
Test Dask distributed batch processing vs ThreadPoolExecutor

Demonstrates the performance improvement of Dask for large batch embeddings.
"""
import sys
import time
sys.path.insert(0, "/home/joker/SOLLOL/src")

from sollol import OllamaPool

def test_dask_batch():
    """Test Dask distributed batch embedding"""
    print("\n" + "="*80)
    print("SOLLOL Dask Distributed Batch Processing Test")
    print("="*80)

    # Test 1: Pool with Dask enabled
    print("\n📊 Test 1: Creating pool with Dask enabled...")
    pool = OllamaPool.auto_configure(enable_dask=True, enable_cache=False)

    stats = pool.get_stats()
    print(f"\n✅ Pool initialized:")
    print(f"   Nodes: {stats['nodes_configured']}")
    print(f"   Dask enabled: {stats['dask']['enabled']}")

    if stats['dask']['enabled']:
        print(f"   Dask workers: {stats['dask'].get('workers', 'unknown')}")
        print(f"   Dask dashboard: {stats['dask'].get('dashboard', 'N/A')}")

    # Test 2: Small batch embedding with Dask
    print("\n📊 Test 2: Small batch embedding (10 texts)...")
    small_batch = [f"Test embedding text {i}" for i in range(10)]

    start = time.time()
    results = pool.embed_batch(
        model="mxbai-embed-large",
        inputs=small_batch
    )
    duration = time.time() - start

    success_count = sum(1 for r in results if r is not None)
    print(f"\n✅ Small batch complete:")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Success: {success_count}/{len(small_batch)}")
    print(f"   Throughput: {success_count/duration:.1f} embeddings/sec")

    # Test 3: Medium batch embedding
    print("\n📊 Test 3: Medium batch embedding (50 texts)...")
    medium_batch = [f"Test embedding text {i}" for i in range(50)]

    start = time.time()
    results = pool.embed_batch(
        model="mxbai-embed-large",
        inputs=medium_batch
    )
    duration = time.time() - start

    success_count = sum(1 for r in results if r is not None)
    print(f"\n✅ Medium batch complete:")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Success: {success_count}/{len(medium_batch)}")
    print(f"   Throughput: {success_count/duration:.1f} embeddings/sec")

    # Test 4: Large batch embedding
    print("\n📊 Test 4: Large batch embedding (100 texts)...")
    large_batch = [f"Test embedding text {i}" for i in range(100)]

    start = time.time()
    results = pool.embed_batch(
        model="mxbai-embed-large",
        inputs=large_batch
    )
    duration = time.time() - start

    success_count = sum(1 for r in results if r is not None)
    print(f"\n✅ Large batch complete:")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Success: {success_count}/{len(large_batch)}")
    print(f"   Throughput: {success_count/duration:.1f} embeddings/sec")

    # Test 5: Comparison with Dask disabled
    print("\n📊 Test 5: Comparison - Creating pool with Dask disabled...")
    pool_no_dask = OllamaPool.auto_configure(enable_dask=False, enable_cache=False)

    stats_no_dask = pool_no_dask.get_stats()
    print(f"\n✅ Pool initialized (no Dask):")
    print(f"   Nodes: {stats_no_dask['nodes_configured']}")
    print(f"   Dask enabled: {stats_no_dask['dask']['enabled']}")

    print("\n📊 Test 5b: Same medium batch with ThreadPoolExecutor only...")
    start = time.time()
    results_no_dask = pool_no_dask.embed_batch(
        model="mxbai-embed-large",
        inputs=medium_batch
    )
    duration_no_dask = time.time() - start

    success_count_no_dask = sum(1 for r in results_no_dask if r is not None)
    print(f"\n✅ ThreadPoolExecutor batch complete:")
    print(f"   Duration: {duration_no_dask:.2f}s")
    print(f"   Success: {success_count_no_dask}/{len(medium_batch)}")
    print(f"   Throughput: {success_count_no_dask/duration_no_dask:.1f} embeddings/sec")

    # Comparison
    if stats['dask']['enabled'] and duration > 0 and duration_no_dask > 0:
        speedup = duration_no_dask / duration
        print(f"\n🚀 Dask Performance Gain:")
        print(f"   Speedup: {speedup:.2f}x faster than ThreadPoolExecutor")

    # Final stats
    print("\n📊 Final Pool Stats:")
    final_stats = pool.get_stats()
    print(f"   Total requests: {final_stats['total_requests']}")
    print(f"   Successful: {final_stats['successful_requests']}")
    print(f"   Failed: {final_stats['failed_requests']}")

    # Cleanup
    pool.stop()
    pool_no_dask.stop()

    print("\n✅ All tests completed!")
    print("="*80)

if __name__ == "__main__":
    try:
        test_dask_batch()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
