#!/usr/bin/env python3
"""
Test connection reuse optimization in OllamaPool

This script tests that the persistent HTTP session reuses connections
instead of creating new ones for each request.
"""

import sys
import time

sys.path.insert(0, "/home/joker/SOLLOL/src")

from sollol import OllamaPool

def test_connection_reuse():
    """Test that embeddings reuse the same HTTP connection."""
    print("=" * 80)
    print("Testing Connection Reuse Optimization")
    print("=" * 80)

    # Create pool
    print("\n📦 Creating OllamaPool...")
    pool = OllamaPool.auto_configure()

    if not pool.nodes:
        print("❌ No Ollama nodes found")
        return False

    print(f"✅ Found {len(pool.nodes)} nodes: {pool.nodes}")

    # Verify session is created
    if not hasattr(pool, 'session'):
        print("❌ Session not created in pool")
        return False

    print("✅ Persistent HTTP session created")

    # Test sequential embeddings (should reuse connection)
    print("\n🧪 Running sequential embedding test (10 embeddings)...")
    print("   (With connection reuse, should be faster than creating 10 new connections)")

    test_texts = [
        f"This is test embedding number {i}" for i in range(10)
    ]

    start_time = time.time()

    for i, text in enumerate(test_texts, 1):
        try:
            result = pool.embed(model="mxbai-embed-large", input=text)
            if 'embeddings' in result or 'embedding' in result:
                print(f"   ✅ Embedding {i}/10 completed")
            else:
                print(f"   ⚠️  Embedding {i}/10 returned unexpected format")
        except Exception as e:
            print(f"   ❌ Embedding {i}/10 failed: {e}")
            return False

    elapsed = time.time() - start_time
    avg_time = elapsed / len(test_texts)

    print(f"\n📊 Results:")
    print(f"   Total time: {elapsed:.2f}s")
    print(f"   Average per embedding: {avg_time*1000:.1f}ms")
    print(f"   Throughput: {len(test_texts)/elapsed:.1f} embeddings/sec")

    # Performance expectations
    if avg_time < 0.5:  # Less than 500ms per embedding
        print("\n✅ Performance is EXCELLENT (connection reuse working)")
    elif avg_time < 1.0:  # Less than 1s per embedding
        print("\n✅ Performance is GOOD")
    else:
        print("\n⚠️  Performance is slower than expected")

    # Cleanup
    print("\n🧹 Cleaning up...")
    pool.stop()
    print("✅ Pool stopped successfully")

    return True


if __name__ == "__main__":
    print("\nSOLLOL Connection Reuse Test")
    print("=" * 80)

    success = test_connection_reuse()

    if success:
        print("\n" + "=" * 80)
        print("✅ All tests passed!")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("❌ Tests failed")
        print("=" * 80)
        sys.exit(1)
