#!/usr/bin/env python3
"""
Fair comparison: Dask vs ThreadPoolExecutor for batch embeddings

Tests with warmed-up pools on same batch sizes.
"""
import sys
import time
sys.path.insert(0, "/home/joker/SOLLOL/src")

from sollol import OllamaPool

def test_comparison():
    """Fair comparison of Dask vs ThreadPoolExecutor"""
    print("\n" + "="*80)
    print("SOLLOL: Dask vs ThreadPoolExecutor Comparison")
    print("="*80)

    # Create both pools
    print("\n📊 Creating pools...")
    pool_dask = OllamaPool.auto_configure(enable_dask=True, enable_cache=False)
    pool_threads = OllamaPool.auto_configure(enable_dask=False, enable_cache=False)

    # Warm up both pools (first request initializes workers)
    print("\n🔥 Warming up both pools...")
    warmup = ["warmup text"]
    pool_dask.embed_batch("mxbai-embed-large", warmup)
    pool_threads.embed_batch("mxbai-embed-large", warmup)
    print("✅ Warmup complete")

    # Test batch sizes
    batch_sizes = [25, 50, 100, 200]

    results = []

    for size in batch_sizes:
        print(f"\n{'='*80}")
        print(f"📊 Batch Size: {size} texts")
        print(f"{'='*80}")

        batch = [f"Test embedding text number {i}" for i in range(size)]

        # Test Dask
        print(f"\n⚡ Testing Dask...")
        start = time.time()
        dask_results = pool_dask.embed_batch("mxbai-embed-large", batch)
        dask_duration = time.time() - start
        dask_success = sum(1 for r in dask_results if r is not None)
        dask_throughput = dask_success / dask_duration

        print(f"   Duration: {dask_duration:.2f}s")
        print(f"   Success: {dask_success}/{size}")
        print(f"   Throughput: {dask_throughput:.1f} emb/sec")

        # Test ThreadPoolExecutor
        print(f"\n🧵 Testing ThreadPoolExecutor...")
        start = time.time()
        thread_results = pool_threads.embed_batch("mxbai-embed-large", batch)
        thread_duration = time.time() - start
        thread_success = sum(1 for r in thread_results if r is not None)
        thread_throughput = thread_success / thread_duration

        print(f"   Duration: {thread_duration:.2f}s")
        print(f"   Success: {thread_success}/{size}")
        print(f"   Throughput: {thread_throughput:.1f} emb/sec")

        # Calculate speedup
        speedup = thread_duration / dask_duration
        print(f"\n🚀 Dask Speedup: {speedup:.2f}x")

        results.append({
            'size': size,
            'dask_throughput': dask_throughput,
            'thread_throughput': thread_throughput,
            'speedup': speedup
        })

    # Summary
    print(f"\n{'='*80}")
    print("📈 SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Size':<10} {'Dask (emb/s)':<15} {'Thread (emb/s)':<15} {'Speedup':<10}")
    print("-" * 50)

    for r in results:
        print(f"{r['size']:<10} {r['dask_throughput']:<15.1f} {r['thread_throughput']:<15.1f} {r['speedup']:<10.2f}x")

    avg_speedup = sum(r['speedup'] for r in results) / len(results)
    print(f"\nAverage Dask speedup: {avg_speedup:.2f}x")

    # Get cluster info
    stats = pool_dask.get_stats()
    if stats['dask']['enabled']:
        print(f"\n📊 Dask Cluster:")
        print(f"   Workers: {stats['dask'].get('workers', 'unknown')}")
        print(f"   Dashboard: {stats['dask'].get('dashboard', 'N/A')}")

    # Cleanup
    pool_dask.stop()
    pool_threads.stop()

    print("\n✅ Test complete!")
    print("="*80)

if __name__ == "__main__":
    try:
        test_comparison()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
