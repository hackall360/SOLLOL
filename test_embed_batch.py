#!/usr/bin/env python3
"""
Test SOLLOL embed_batch() performance improvement.
"""
import time
from sollol import OllamaPool

# Create pool
pool = OllamaPool.auto_configure()

# Test data - 20 sample texts
texts = [
    f"This is test chunk number {i} with some sample text to embed."
    for i in range(20)
]

print(f"🧪 Testing embed_batch() with {len(texts)} texts")
print(f"📊 Nodes: {len(pool.nodes)}")
nodes_list = [f"{n['host']}:{n['port']}" for n in pool.nodes]
print(f"   {nodes_list}")
print()

# Test batch processing
start_time = time.time()
results = pool.embed_batch("mxbai-embed-large", texts)
batch_time = time.time() - start_time

# Count successful embeddings
success_count = sum(1 for r in results if r is not None)

print()
print("=" * 70)
print(f"✅ Batch embedding complete!")
print(f"   Successful: {success_count}/{len(texts)}")
print(f"   Total time: {batch_time:.2f}s")
print(f"   Avg per text: {batch_time/len(texts):.3f}s")
print(f"   Throughput: {len(texts)/batch_time:.1f} texts/sec")
print("=" * 70)

# Show pool stats
stats = pool.get_stats()
print(f"\n📊 Pool Stats:")
print(f"   Total requests: {stats['total_requests']}")
print(f"   Successful: {stats['successful_requests']}")
print(f"   Failed: {stats['failed_requests']}")
