#!/usr/bin/env python3
"""
Test adaptive Dask routing - automatically chooses best strategy
"""
import sys
import time
sys.path.insert(0, "/home/joker/SOLLOL/src")

from sollol import OllamaPool

def test_adaptive():
    """Test adaptive batch routing"""
    print("\n" + "="*80)
    print("SOLLOL: Adaptive Dask Routing Test")
    print("="*80)

    # Create pool with Dask enabled
    print("\n📊 Creating pool with Dask enabled...")
    pool = OllamaPool.auto_configure(enable_dask=True, enable_cache=False)

    stats = pool.get_stats()
    print(f"✅ Pool initialized:")
    print(f"   Nodes: {stats['nodes_configured']}")
    print(f"   Dask enabled: {stats['dask']['enabled']}")
    print(f"   Dask workers: {stats['dask'].get('workers', 'unknown')}")

    # Warm up
    print("\n🔥 Warming up...")
    pool.embed_batch("mxbai-embed-large", ["warmup"])

    # Test different batch sizes
    test_cases = [
        (25, "Small batch - should use ThreadPoolExecutor"),
        (50, "Medium batch - should use ThreadPoolExecutor"),
        (150, "Large batch - should use Dask"),
        (300, "Very large batch - should use Dask"),
    ]

    print("\n" + "="*80)
    print("Testing adaptive routing on different batch sizes:")
    print("="*80)

    for size, description in test_cases:
        print(f"\n📊 {description}")
        print(f"   Batch size: {size} texts")

        batch = [f"Test text {i}" for i in range(size)]

        start = time.time()
        results = pool.embed_batch("mxbai-embed-large", batch)
        duration = time.time() - start

        success = sum(1 for r in results if r is not None)
        throughput = success / duration

        print(f"   ✅ Complete: {duration:.2f}s ({throughput:.1f} emb/sec)")

    pool.stop()

    print("\n✅ Adaptive routing test complete!")
    print("="*80)

if __name__ == "__main__":
    try:
        test_adaptive()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
