"""
Example: Adaptive Parallelism with SOLLOL

This example demonstrates how SOLLOL automatically chooses between
sequential and parallel processing based on cluster characteristics.

Key Features:
- Auto-detects GPU nodes and their capabilities
- Decides sequential vs parallel based on:
  - GPU performance gap (5x+ faster = sequential)
  - Batch size (<20 = sequential)
  - Cluster balance (similar nodes = parallel)
- VRAM-aware model routing
- Dynamic model discovery
"""

import time
from sollol import OllamaPool

def example_basic_batch():
    """Basic batch processing with adaptive parallelism."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Batch Processing")
    print("="*70)

    # Create pool with all features enabled (default)
    pool = OllamaPool.auto_configure()

    # Prepare batch of chat requests
    messages_list = [
        [{"role": "user", "content": f"Tell me a fact about number {i}"}]
        for i in range(10)
    ]

    # SOLLOL automatically decides: sequential or parallel?
    print("\n🤖 Processing 10 chat requests...")
    start = time.time()
    responses = pool.batch_chat("llama3.2", messages_list, priority=5)
    elapsed = time.time() - start

    print(f"\n✅ Completed in {elapsed:.2f}s")
    print(f"📊 Successful: {sum(1 for r in responses if 'error' not in r)}/{len(responses)}")

    # Show first response
    if responses and 'error' not in responses[0]:
        print(f"\n💬 First response preview:")
        content = responses[0]['message']['content'][:100]
        print(f"   {content}...")


def example_small_batch():
    """Small batch (sequential processing expected)."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Small Batch (Sequential Expected)")
    print("="*70)

    pool = OllamaPool.auto_configure()

    # Small batch of 3 requests
    messages_list = [
        [{"role": "user", "content": "What is AI?"}],
        [{"role": "user", "content": "What is ML?"}],
        [{"role": "user", "content": "What is DL?"}],
    ]

    print("\n🤖 Processing 3 chat requests (small batch)...")
    print("   Expected: SEQUENTIAL (overhead not worth it)")

    start = time.time()
    responses = pool.batch_chat("llama3.2", messages_list)
    elapsed = time.time() - start

    print(f"\n✅ Completed in {elapsed:.2f}s")


def example_large_batch_embeddings():
    """Large batch of embeddings (parallel expected)."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Large Embedding Batch (Parallel Expected)")
    print("="*70)

    pool = OllamaPool.auto_configure()

    # Generate 50 texts to embed
    texts = [
        f"This is document number {i} about distributed computing and load balancing."
        for i in range(50)
    ]

    print("\n🤖 Processing 50 embedding requests...")
    print("   Expected: PARALLEL (large batch, balanced cluster)")

    start = time.time()
    embeddings = pool.batch_embed("mxbai-embed-large", texts)
    elapsed = time.time() - start

    print(f"\n✅ Completed in {elapsed:.2f}s")
    print(f"📊 Successful: {sum(1 for e in embeddings if 'error' not in e)}/{len(embeddings)}")


def example_manual_control():
    """Example with manual control over features."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Manual Feature Control")
    print("="*70)

    # Create pool with specific features enabled
    pool = OllamaPool(
        enable_intelligent_routing=True,       # Context-aware routing
        enable_adaptive_parallelism=True,      # Adaptive seq/parallel
        enable_vram_management=True,           # VRAM-aware routing
    )

    print(f"\n📊 Pool configuration:")
    print(f"   Nodes: {len(pool.nodes)}")
    print(f"   Intelligent routing: {pool.enable_intelligent_routing}")
    print(f"   Adaptive parallelism: {pool.enable_adaptive_parallelism}")
    print(f"   VRAM management: {pool.enable_vram_management}")

    # Process a batch
    messages_list = [
        [{"role": "user", "content": f"Question {i}"}]
        for i in range(5)
    ]

    responses = pool.batch_chat("llama3.2", messages_list)
    print(f"\n✅ Processed {len(responses)} requests")


def example_stats_and_monitoring():
    """Example showing stats and monitoring."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Stats and Monitoring")
    print("="*70)

    pool = OllamaPool.auto_configure()

    # Make some requests
    pool.chat("llama3.2", [{"role": "user", "content": "Hello"}])
    pool.chat("llama3.2", [{"role": "user", "content": "How are you?"}])

    # Get stats
    stats = pool.get_stats()
    print(f"\n📊 Pool Statistics:")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Successful: {stats['successful_requests']}")
    print(f"   Failed: {stats['failed_requests']}")
    print(f"   Nodes: {stats['nodes']}")

    print(f"\n📈 Per-Node Performance:")
    for node_key, perf in stats['node_performance'].items():
        print(f"   {node_key}:")
        print(f"      Avg latency: {perf['latency_ms']:.1f}ms")
        print(f"      Success rate: {perf['success_rate']:.1%}")
        print(f"      Total requests: {perf['total_requests']}")
        print(f"      Has GPU: {perf.get('has_gpu', 'unknown')}")


def example_gpu_capabilities():
    """Example showing GPU capability detection."""
    print("\n" + "="*70)
    print("EXAMPLE 6: GPU Capabilities")
    print("="*70)

    pool = OllamaPool.auto_configure()

    # Wait a moment for background GPU detection
    time.sleep(2)

    if pool.gpu_controller:
        print("\n💾 GPU Capabilities:")

        # Show VRAM capabilities
        pool.gpu_controller.print_vram_capabilities()

        # Show discovered models
        print("\n📚 Discovered Models:")
        models = pool.gpu_controller.discover_all_models()
        for model_name, metadata in list(models.items())[:5]:  # Show first 5
            size_mb = metadata.get('size_mb', 0)
            print(f"   {model_name}: {size_mb}MB")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("SOLLOL ADAPTIVE PARALLELISM EXAMPLES")
    print("="*70)
    print("\nThese examples demonstrate SOLLOL's intelligent batch processing")
    print("that automatically chooses sequential vs parallel based on:")
    print("  1. GPU performance gap")
    print("  2. Batch size")
    print("  3. Cluster characteristics")
    print("\n" + "="*70)

    try:
        example_basic_batch()
        example_small_batch()
        example_large_batch_embeddings()
        example_manual_control()
        example_stats_and_monitoring()
        example_gpu_capabilities()

        print("\n" + "="*70)
        print("✅ ALL EXAMPLES COMPLETED")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Ollama is running (ollama serve)")
        print("  2. Required models are pulled:")
        print("     - ollama pull llama3.2")
        print("     - ollama pull mxbai-embed-large")


if __name__ == "__main__":
    main()
