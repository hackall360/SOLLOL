#!/usr/bin/env python3
"""
Example: Using Node Clusters for Large Model Inference

Demonstrates:
1. Setting up node registry
2. Creating clusters for large models
3. Smart routing (large models → clusters, small models → individual nodes)
4. Running distributed inference
"""
import asyncio
import logging
from sollol.registry import NodeRegistry
from sollol.node_cluster import needs_partitioning

logging.basicConfig(level=logging.INFO)


async def main():
    print("=" * 70)
    print("SOLLOL Layer Partitioning Example")
    print("=" * 70)

    # 1. Create registry and add nodes
    print("\n📋 Setting up node registry...")
    registry = NodeRegistry()

    # Add nodes (replace with your actual node URLs)
    nodes_to_add = [
        ("http://192.168.1.10:11434", "gpu-node-1"),
        ("http://192.168.1.11:11434", "gpu-node-2"),
        ("http://192.168.1.12:11434", "gpu-node-3"),
    ]

    for url, name in nodes_to_add:
        try:
            registry.add_node(url, name=name, check_health=True)
        except Exception as e:
            print(f"⚠️  Could not add {name}: {e}")

    print(f"\n{registry}")
    print(f"Healthy nodes: {len(registry.get_healthy_nodes())}")

    # 2. Create cluster for large model
    if len(registry.get_healthy_nodes()) >= 2:
        print("\n🔗 Creating cluster for Llama-70B...")

        cluster = registry.create_cluster(
            name="llama70b-cluster",
            node_urls=[
                registry.get_healthy_nodes()[0].url,
                registry.get_healthy_nodes()[1].url
            ],
            model="llama2:70b",
            partitioning_strategy="even"
        )

        print(f"\nCluster created: {cluster}")
        print(f"Partitions:")
        for i, partition in enumerate(cluster.partitions):
            print(
                f"  Node {i+1} ({partition.node_url}): "
                f"layers {partition.start_layer}-{partition.end_layer-1} "
                f"({partition.layer_count} layers)"
            )

        # 3. Check cluster health
        print("\n🏥 Checking cluster health...")
        is_healthy = await cluster.health_check()
        print(f"Cluster healthy: {is_healthy}")

        # 4. Run inference on cluster
        if is_healthy:
            print("\n💬 Running distributed inference...")
            print("Prompt: 'Explain quantum computing in detail'\n")

            try:
                result = await cluster.generate(
                    prompt="Explain quantum computing in detail",
                    options={"temperature": 0.7, "num_predict": 100}
                )

                print("Response:")
                print(result.get('response', 'No response'))
                print(f"\nCluster metadata: {result.get('_cluster', {})}")

            except Exception as e:
                print(f"❌ Inference failed: {e}")
                print("Note: This requires Ollama layer partitioning support")

    else:
        print("\n⚠️  Not enough healthy nodes for clustering (need 2+)")

    # 5. Demonstrate smart routing
    print("\n" + "=" * 70)
    print("🎯 Smart Routing Demo")
    print("=" * 70)

    models_to_test = [
        "llama3.2",      # Small model → individual node
        "llama2:70b",    # Large model → cluster
        "phi",           # Small model → individual node
        "mixtral:8x7b"   # Large model → cluster
    ]

    for model in models_to_test:
        worker = registry.get_worker_for_model(model)
        needs_cluster = needs_partitioning(model)

        if worker:
            worker_type = "Cluster" if hasattr(worker, 'partitions') else "Node"
            print(
                f"\n{model:20} → {worker_type:10} "
                f"({worker.name}) "
                f"[Needs partitioning: {needs_cluster}]"
            )
        else:
            print(f"\n{model:20} → No worker available")

    # 6. Show registry state
    print("\n" + "=" * 70)
    print("📊 Final Registry State")
    print("=" * 70)
    print(f"{registry}")
    print(f"\nNodes: {len(registry.nodes)}")
    for url, node in registry.nodes.items():
        print(f"  • {node.name:15} {url:30} {'✓' if node.is_healthy else '✗'}")

    print(f"\nClusters: {len(registry.clusters)}")
    for name, cluster in registry.clusters.items():
        print(
            f"  • {cluster.name:15} {cluster.model:15} "
            f"{len(cluster.nodes)} nodes  {'✓' if cluster.is_healthy else '✗'}"
        )


if __name__ == "__main__":
    print("""
NOTE: This example requires:
1. Multiple Ollama instances running on your network
2. Sufficient GPU memory across nodes for the model
3. Ollama layer partitioning support (upcoming feature)

For testing without actual clusters:
- The code demonstrates cluster creation and routing logic
- Inference will fail gracefully without Ollama layer support
- Smart routing will still work correctly
    """)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
